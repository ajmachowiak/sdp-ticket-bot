import os
import sys
import config
import logging

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
    """Parses engineers.md and returns a list of active UPNs."""
    if not os.path.exists(file_path):
        logging.error(f"Roster file '{file_path}' not found.")
        return[]

    active_engineers = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # skip empty lines, headers and commented-out users
            if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue
            active_engineers.append(stripped)

    return active_engineers

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
                template_name, technician = stripped.split(":", 1)
                rota_data[template_name.strip()] = technician.strip()

    return rota_data

# rotates assigned engineers to next active engineer
def rotate_assignments(active_engineers, current_rota):
    """Rotates assigned engineers to the next active engineer using Modulo Arithmetic."""
    if not active_engineers:
        logging.error("Cannot rotate. Active engineer pool is empty.")
        return current_rota

    num_engineers = len(active_engineers)
    new_rota = {}

    for template, current_tech in current_rota.items():
        if current_tech in active_engineers:
            # find engineers current index in active pool
            current_index = active_engineers.index(current_tech)

            # modulo arithmetic shifts to the next index and wraps around to 0 at the end
            next_index = (current_index + 1) % num_engineers
            new_rota[template] = active_engineers[next_index]
        else:
            # fallback: if assigned engineer went on leave, assign the first available active engineer
            logging.warning(f"'{current_tech} for '{template}' is away. Fallback assigned to '{active_engineers[0]}'")
            new_rota[template] = active_engineers[0]

    return new_rota

# overwrites rota.md with newly rotated assignments
def save_rota_file(new_rota, file_path=config.ROTA_FILE):
    """Overwrites rota.md with the newly rotated assignments."""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write('# Live Rota Mapping\n\n')
        for template, tech in new_rota.items():
            f.write(f"{template}: {tech}\n")
    logging.info(" Successfully updated rota.md!")

def main():
    active_engineers = get_active_engineers()
    current_rota = read_rota_file()

    if not current_rota:
        logging.info("No valid rota assignments found to rotate.")
        return

    logging.info(f"Active Pool ({len(active_engineers)}): {active_engineers}")
    updated_rota = rotate_assignments(active_engineers, current_rota)

    logging.info("\nProposed Rota Shift:")
    for template, tech in updated_rota.items():
        logging.info(f"  {template} -> {tech}")

    save_rota_file(updated_rota)

if __name__ == "__main__":
    main()