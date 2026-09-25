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
from concurrent.futures import ThreadPoolExecutor

from rota_helper import (
    get_active_engineers,
    read_rota_file,
    save_rota_file,
    get_next_engineer
)

# setup logging to output to both console and a log file
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

    parser.add_argument(
        "--test",
        action="store_true",
        help="Prepend [TESTING] to the ticket subject for real API test runs."
    )

    return parser.parse_args()

# date calculation helper
def get_template_variables():
    today = datetime.now()
    # calculate the monday of the current week
    monday = today - timedelta(days=today.weekday())

    return {
        "{{ WEEK_COMMENCING }}": monday.strftime("%d/%m/%Y"), # the first day of the week (Monday)
        "{{ WEEK_ENDING }}": (monday + timedelta(days=4)).strftime("%d/%m/%Y"), # the last day of the week (Friday)
        "{{ CURRENT_DATE }}": today.strftime("%d/%m/%Y"), # the current date
         # for below,modify to your preferred specific date (if needed), change the "3" variable to what is needed (0 = Monday, 4 = Friday) and the "THURSDAY" text to your specific day
        "{{ THURSDAY_DATE }}": (monday + timedelta(days=3)).strftime("%d/%m/%Y"), # Thursday of the current week
        "{{ MONTH }}": today.strftime("%B"), # the current month name
        "{{ YEAR }}": str(today.year) # the current year
    }

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

        current_key = None
        # parse key value metadata pairs line by line
        for line in raw_metadata.split("\n"):
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue

            # handle list items under a key (e.g. - engineer.one@company.com)
            if stripped_line.startswith("- ") and current_key:
                val = stripped_line[2:].strip()
                if not isinstance(metadata[current_key], list):
                    metadata[current_key] = []
                metadata[current_key].append(val)
            elif ":" in line:
                key, value = line.split(":", 1)
                current_key = key.strip()
                val = value.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                metadata[current_key] = val if val else []

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
def create_sdp_ticket(parsed_template, assigned_engineer, access_token=None,dry_run=False, is_test=False):
    """Builds SDP JSON payload and sends POST request or prints dry-run output."""
    metadata = parsed_template["metadata"]

    # prepend [TESTING] to template title if --test flag is used
    title = metadata.get("title", "Automated Task")
    subject = f"[TESTING] {title}" if is_test else title
    template_name = metadata.get("sdp_template", getattr(config, "SDP_TEMPLATE", "Default Request"))

    # structure of payload to SDP API spec
    input_data = {
        "request": {
            "subject": subject,
            "description": parsed_template["html_body"],
            "template": {"name": template_name},
            "requester": {"email_id": config.SDP_REQUESTER_EMAIL},
            "site": {"name": metadata.get("site", config.SDP_SITE)},
            "group": {"name": metadata.get("group", config.SDP_GROUP)},
            "category": {"name": metadata.get("category", config.SDP_CATEGORY)},
            "request_type": {"name": config.SDP_REQUEST_TYPE},
            "mode": {"name": config.SDP_MODE},
            "impact": {"name": config.SDP_IMPACT},
            "urgency": {"name": config.SDP_URGENCY},
            "priority": {"name": metadata.get("priority", config.SDP_PRIORITY)},
            "technician": {"email_id": assigned_engineer} if assigned_engineer != "Unassigned" else None,
        }
    }

    # structure of what is printed on --dry-run
    if dry_run:
        logging.info(f" DRY RUN MODE - Ticket payload generated for '{parsed_template['file_name']}':")
        logging.info(f"Target URL: {config.SDP_BASE_URL}/api/v3/requests")
        logging.info(f"Subject: {input_data['request']['subject']}")
        logging.info(f"Assigned To: {assigned_engineer}")
        logging.info(f"Category: {input_data['request']['category']['name']}")
        logging.info("Payload Structure:")
        logging.info(json.dumps(input_data, indent=2))
        logging.info("-" * 50)
        return True

    # real execution path (runs when dry_run is False)
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Accept": "application/vnd.manageengine.sdp.v3+json"
    }

    # SDP API requires input_data as form parameter string
    payload = {"input_data": json.dumps(input_data)}
    endpoint = f"{config.SDP_BASE_URL}/api/v3/requests"

    response = requests.post(endpoint, headers=headers, data=payload)
    if response.status_code in (200, 201):
        try:
            res_data = response.json()
            request_info = res_data.get("request", {})

            # SDP returns ticket number
            ticket_id = (
                request_info.get("display_id")
                or request_info.get("id")
                or "N/A"
            )
            logging.info(f"     Successfully created ticket #{ticket_id} for {parsed_template['file_name']}")
        except Exception:
            logging.info(f"     Successfully created ticket for '{parsed_template['file_name']}' (Could not parse Ticket ID)")
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
    rota_mappings = read_rota_file()

    logging.info(f"Active Engineers: {len(active_engineers)}")
    logging.info(f"Processing {len(template_files)} templates(s) from '{template_dir}':\n")

    # fetch OAuth Token ONCE for all worker threads
    access_token = None
    if not args.dry_run:
        access_token = get_sdp_access_token()

    dispatch_jobs = []

    # phase 1: sequential rota state computation
    used_engineers = set() # tracks engineers assigned in this batch run

    for file_path in template_files:
        parsed_data = parse_template_file(file_path)

        # skip template if marked as "draft: true" in metadata
        if parsed_data['metadata'].get('draft') == 'true':
            logging.info(f"Skipping draft template: {parsed_data['file_name']}")
            continue

        file_name = parsed_data['file_name']

        # determine engineer using site filtering and rotation
        assigned_engineer = get_next_engineer(
            template_filename=file_name,
            template_metadata=parsed_data['metadata'],
            active_roster=active_engineers,
            current_rota=rota_mappings,
            used_engineers=used_engineers
        )

        # update in memory rota state
        rota_mappings[file_name] = assigned_engineer
        dispatch_jobs.append((parsed_data, assigned_engineer))

        # phase 2: parallel ticket creation using ThreadPoolExecutor
        # adjust max_workers (e.g. 5) based on your network and SDP rate limits
    if dispatch_jobs:
        max_workers = min(5, len(dispatch_jobs))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    create_sdp_ticket,
                    parsed_data,
                    assigned_engineer,
                    access_token,
                    args.dry_run,
                    args.test
                )
                for parsed_data, assigned_engineer in dispatch_jobs
            ]

            # wait for all thread tasks to complete
            for future in futures:
                future.result()

    # save updated assignments back to rota.md
    if not args.dry_run:
        save_rota_file(rota_mappings)

if __name__ == "__main__":
    main()