import os
import sys
import config
import logging
import glob

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

# cleans engineers.md, ignoring commented-out engineers and only picking up active
def get_active_engineers(file_path=config.ENGINEERS_FILE):
    """Parses engineers.md and returns a dictionary mapping site names (and 'all') to lists of active engineer UPNs."""
    if not os.path.exists(file_path):
        logging.error(f"Roster file '{file_path}' not found.")
        return {"allsites": []}

    roster = {"allsites": []}
    current_selection = "allsites"
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            if stripped.startswith("##"):
                current_selection = stripped.lstrip("#").replace(" ", "").strip().lower()
                if current_selection not in roster:
                    roster[current_selection] = []
                continue

            # skip empty lines, headers and commented-out users
            if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue

            # parse engineer list item
            if stripped.startswith("- "):
                email = stripped[2:].strip()
                # exclude inline commented lines
                if not email.startswith("#") and not email.startswith("<!--"):
                    roster[current_selection].append(email)

    return roster

# reads rota.md and extracts template to engineer pairs
def read_rota_file(file_path=config.ROTA_FILE):
    """Reads rota.md and extracts template-to-engineer pairs."""
    if not os.path.exists(file_path):
        logging.error(f"Rota file '{file_path}' not found.")
        return {}

    rota_data = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # skip empty lines, headers and commented-out users
            if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue
            if ":" in stripped:
                template_name, engineer = stripped.split(":", 1)
                rota_data[template_name.strip()] = engineer.strip()

    return rota_data

# filters active engineers by site (if site_engineers exists in the template_metadata) and returns the next engineer based on rota.md tracking
def get_next_engineer(template_filename, template_metadata, active_roster, current_rota, used_engineers=None):
    """Determines the next engineer by matching the templates 'site' frontmatter key against the parsed site pools in engineers.md."""
    if used_engineers is None:
        used_engineers = set()

    # get site name, if exists, and lowercase it
    raw_site = template_metadata.get("site")
    site_key = str(raw_site).strip().lower() if raw_site else ""

    # 1. select pool strictly based on whether 'site' exists
    if site_key:
        eligible_pool = active_roster.get(site_key, [])
        if not eligible_pool:
            return "Unassigned"
    else:
        eligible_pool = active_roster.get("allsites", [])
        if not eligible_pool:
            return "Unassigned"

    # 2. pick unused engineers first
    # if everyone was used or only 1 engineer exists, use full pool
    unused = [eng for eng in eligible_pool if eng not in used_engineers]
    pool = unused if unused else eligible_pool

    # 3. rotate to next engineer based on historical rota
    last = current_rota.get(template_filename)
    if last in pool:
        idx = (pool.index(last) + 1) % len(pool)
    else:
        idx = sum(ord(c) for c in template_filename) % len(pool)

    chosen = pool[idx]
    used_engineers.add(chosen)
    return chosen

# overwrites rota.md with newly rotated assignments
def save_rota_file(new_rota, file_path=config.ROTA_FILE):
    """Overwrites rota.md with the newly rotated assignments whilst preserving all existing headers, comments and line formatting."""
    if not os.path.exists(file_path):
        # fallback if rota.md doesn't exist, create a new one with a header
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Live Rota Mapping\n\n")
            for template_name, assigned_engineer in new_rota.items():
                f.write(f"{template_name}: {assigned_engineer}\n")
        logging.info("Created new rota.md file.")
        return

    # read original file contents line by line
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_lines = []
    for line in lines:
        stripped = line.strip()

        # preserve empty lines, section headers and comments as-is
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            updated_lines.append(line)
            continue

        # if its a template mapping line, check and update assigned engineer
        if ":" in line:
            template_name, _ = line.split(":", 1)
            clean_name = template_name.strip()

            if clean_name in new_rota:
                # reconstruct line preserving original template key format
                updated_lines.append(f"{clean_name}: {new_rota[clean_name]}\n")
            else:
                updated_lines.append(line)  # keep the line as-is if not in new_rota
        else:
            updated_lines.append(line)  # keep the line as-is if it doesn't match expected format

    # write back the full file with comments intact
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    logging.info("  Successfully updated rota.md with new assignments.")

def main():
    from app import parse_template_file

    active_engineers = get_active_engineers()
    current_rota = read_rota_file()

    if not current_rota:
        logging.info("No valid rota assignments found to rotate.")
        return

    logging.info(f"Active Pool ({len(active_engineers)}): {active_engineers}")
    updated_rota = current_rota.copy()

    for schedule in ["weekly", "monthly"]:
        schedule_dir = os.path.join(config.TEMPLATES_DIR, schedule)
        if not os.path.exists(schedule_dir):
            continue

        template_files = glob.glob(os.path.join(schedule_dir, "*.md"))
        if not template_files:
            continue

        used_general_engineers = set()
        used_site_engineers = set()

        for file_path in template_files:
            parsed_data = parse_template_file(file_path)

            # skip template if marked as "draft: true" in metadata
            if parsed_data['metadata'].get('draft') == 'true':
                continue

            file_name = parsed_data['file_name']

            # only update assignments for templates tracked in rota.md
            if file_name in updated_rota:

                is_site_specific = bool(parsed_data['metadata'].get('site'))

                active_used_set = used_site_engineers if is_site_specific else used_general_engineers

                next_engineer = get_next_engineer(
                    template_filename=file_name,
                    template_metadata=parsed_data['metadata'],
                    active_roster=active_engineers,
                    current_rota=updated_rota,
                    used_engineers=active_used_set
                )
                updated_rota[file_name] = next_engineer

    logging.info("\nProposed Rota Shift:")
    for template_name, assigned_engineer in updated_rota.items():
        logging.info(f"  {template_name} -> {assigned_engineer}")

    save_rota_file(updated_rota)

if __name__ == "__main__":
    main()