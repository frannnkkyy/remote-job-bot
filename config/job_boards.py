"""ATS board lists. Add only board identifiers you have verified."""

# Greenhouse: token at boards.greenhouse.io/<TOKEN> or job-boards.greenhouse.io/<TOKEN>.
# Entry format: ("board_token", "Display Company Name")
GREENHOUSE_BOARDS: list[tuple[str, str]] = []

# Lever: site name at jobs.lever.co/<SITE>. Use "eu:<site>" for jobs.eu.lever.co.
# Entry format: ("site", "Display Company Name")
LEVER_COMPANIES: list[tuple[str, str]] = []

# Ashby: final path segment at jobs.ashbyhq.com/<JOB_BOARD_NAME>.
# Entry format: ("job_board_name", "Display Company Name")
ASHBY_BOARDS: list[tuple[str, str]] = []
