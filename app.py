import argparse
import glob
import os
import re
import sys
from datetime import datetime, timedelta
import requests
import markdown
import json
import logging
import config

# setu logging to output to both console and a log file
log_filename = config.get_log_filename()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# this function is what allows the "--schedule weekly" etc cmds to work
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="SDP Ticket Bot: Automates ticket dispatch based on schedules."
    )

    parser.add_argument(
        "--schedule",
        choices=["weekly", "monthly"], # restricts valid inputs strictly to these 2 options
        required=True, # prevents script from running blindly
        help="Target schedule type (weekly or monthly)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution and print API payloads without creating real tickets."
    )

    return parser.parse_args()

# date calculation helper
def get_template_variables():
    today = datetime.now()
    # calculate the monday of the current week
    monday = today - timedelta(days=today.weekday())

    return {
        "{{ WEEK_COMMENCING }}": monday.strftime("%d/%m/%Y"),
        "{{ CURRENT_DATE }}": today.strftime("%d/%m/%Y"),
        "{{ YEAR }}": str(today.year)
    }

# read and filter active team members from `engineers.md`
def get_active_engineers(file_path=config.ENGINEERS_FILE):
    if not os.path.exists(file_path):
        logging.error(f"{file_path} not found.")
        return []

    active_engineers = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # skip empty lines, headers and commented-out users
            if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue

            active_engineers.append(stripped)

    return active_engineers

# obtain rota assignments
def get_rota_assignments(file_path=config.ROTA_FILE):
    if not os.path.exists(file_path):
        logging.warning(f"{file_path} not found. Tickets will be unassigned.")
        return {}

    assignments = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # skip empty lines, headers and commented-out users
            if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue

            if ":" in stripped:
                template_name, technician = stripped.split(":", 1)
                assignments[template_name.strip()] = technician.strip()

    return assignments

# cleans up the template Md files to work in SDP HTML
def parse_template_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # get calculated runtime var
    variables = get_template_variables()
    # inject dynamic dates into raw temp content
    for placeholder, val in variables.items():
        content = content.replace(placeholder, val)

    # regex to split YAML from Md body
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.search(frontmatter_pattern, content, re.DOTALL) # extracts info between top two "---" as metadata key values, leaving rest as ticket body

    metadata = {}
    markdown_body = content

    if match:
        raw_metadata = match.group(1)
        markdown_body = match.group(2)

        # parse key value metadata pairs line by line
        for line in raw_metadata.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

    # convert Md body into SDP HTML
    html_body = markdown.markdown(markdown_body)

    return {
        "file_name": os.path.basename(file_path),
        "metadata": metadata,
        "html_body": html_body
    }

# add OAuth token fetcher
def get_sdp_access_token():
    """Exchanges refresh token for an active OAuth2 access token."""
    url = f"{config.SDP_ACCOUNTS_URL}/oauth/v2/token"
    params = {
        "refresh_token": config.SDP_REFRESH_TOKEN,
        "client_id": config.SDP_CLIENT_ID,
        "client_secret": config.SDP_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }

    response = requests.post(url, data=params)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        logging.info(f"Failed to fetch OAuth token: {response.text}")
        sys.exit(1)

# SDP ticket creator function
def create_sdp_ticket(parsed_template, assigned_tech, dry_run=False):
    """Builds SDP JSON payload and sends POST request or prints dry-run output."""
    metadata = parsed_template["metadata"]

    # structure of payload to SDP API spec
    input_data = {
        "request": {
            "subject": metadata.get("title", "Scheduled Maintenance Check"),
            "description": parsed_template["html_body"],
            "requester": {"email_id": config.SDP_REQUESTER_EMAIL},
            "category": {"name": metadata.get("category", config.SDP_CATEGORY)},
            "request_type": {"name": config.SDP_REQUEST_TYPE},
            "mode": {"name": config.SDP_MODE},
            "impact": {"name": config.SDP_IMPACT},
            "urgency": {"name": config.SDP_URGENCY},
            "priority": {"name": metadata.get("priority", config.SDP_PRIORITY)},
            "technician": {"email_id": assigned_tech} if assigned_tech != "Unassigned" else None,
        }
    }

    # structure of what is printed on --dry-run
    if dry_run:
        logging.info(f" DRY RUN MODE - Ticket payload generated for '{parsed_template['file_name']}':")
        logging.info(f"Target URL: {config.SDP_BASE_URL}/api/v3/requests")
        logging.info(f"Subject: {input_data['request']['subject']}")
        logging.info(f"Assigned To: {assigned_tech}")
        logging.info(f"Category: {input_data['request']['category']['name']}")
        logging.info("Payload Structure:")
        logging.info(json.dumps(input_data, indent=2))
        logging.info("-" * 50)
        return True

    # real execution path (runs when dry_run is False)
    access_token = get_sdp_access_token()
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Accept": "application/vnd.manageengine.sdp.v3+json"
    }

    # SDP API requires input_data as form parameter string
    payload = {"input_data": json.dumps(input_data)}
    endpoint = f"{config.SDP_BASE_URL}/api/v3/requests"

    response = requests.post(endpoint, headers=headers, data=payload)
    if response.status_code in (200, 201):
        logging.info(f" Successfully created ticket for {parsed_template['filename']}")
        return True
    else:
        logging.info(f" Failed to create ticket. API Response: {response.text}")
        return False

# main part of the app/service
def main():
    args = parse_arguments()

    # construct relative path based on selected choice
    template_dir = os.path.join(config.TEMPLATES_DIR, args.schedule)
    # validate dir existence
    if not os.path.exists(template_dir):
        logging.error(f"Template directory {template_dir} does not exist")
        sys.exit(1)

    # find all Md files in selected dir
    template_files = glob.glob(os.path.join(template_dir, "*.md"))
    if not template_files:
        logging.info(f"No Markdown templates found in '{template_dir}'.")
        return

    active_engineers = get_active_engineers()
    rota_mappings = get_rota_assignments()

    logging.info(f"Active Engineers: {len(active_engineers)}")
    logging.info(f"Processing {len(template_files)} templates(s) from '{template_dir}':\n")

    for file_path in template_files:
        parsed_data = parse_template_file(file_path)
        file_name = parsed_data['file_name']
        # determine assigned engineer from rota.md
        assigned_tech = rota_mappings.get(file_name, "Unassigned")

        # dispatch or simulate ticket creation
        create_sdp_ticket(parsed_data, assigned_tech, dry_run=args.dry_run)

if __name__ == "__main__":
    main()