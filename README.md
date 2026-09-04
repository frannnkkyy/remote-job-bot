# Remote Job Bot

<p>
  <img src="https://img.shields.io/badge/Status-Active-58A96A?style=flat-square" alt="Active">
  <img src="https://img.shields.io/badge/Python-3.12-276FA3?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/GitHub_Actions-Automation-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=flat-square&logo=telegram&logoColor=white" alt="Telegram">
  <img src="https://img.shields.io/badge/Gmail-IMAP-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Gmail">
</p>

Automated job monitoring bot built with **Python** that searches multiple public job sources and sends relevant remote opportunities directly to Telegram.

The bot is focused on **junior technology roles available to candidates in Mexico**, combining multiple job APIs, ATS boards and forwarded job alerts with filtering, scoring and deduplication.

## Overview

Remote Job Bot was developed to automate the repetitive process of searching multiple job platforms for entry-level remote opportunities.

Instead of manually reviewing different job boards, the bot collects vacancies from multiple sources, normalizes their information and evaluates each position using a scoring system.

Only new opportunities that meet the configured criteria are sent through Telegram.

The automation runs every hour through GitHub Actions and maintains a record of previously processed vacancies to prevent duplicate notifications.

## Features

### Job aggregation

- Multiple public job APIs
- Greenhouse job boards
- Lever job boards
- Ashby job boards
- Optional Jobicy integration
- Forwarded job alerts through Gmail
- Independent source adapters
- Fault-tolerant source processing

### Filtering and scoring

- Remote-only filtering
- Mexico, LATAM, Americas and Worldwide compatibility
- Junior and entry-level detection
- Seniority filtering
- Experience requirement analysis
- Technology and role matching
- Publication date scoring
- Configurable minimum score
- Automatic rejection of incompatible locations
- Hybrid and on-site vacancy filtering

### Automation

- Hourly execution with GitHub Actions
- Telegram notifications
- Persistent job deduplication
- Manual workflow execution
- Environment-based configuration
- GitHub Secrets integration
- Automatic persistence of processed vacancies

## Technology stack

| Area | Technologies |
|---|---|
| Core | Python 3.12 |
| HTTP integration | Requests |
| Notifications | Telegram Bot API |
| Email integration | Gmail IMAP |
| Automation | GitHub Actions |
| Job sources | Remotive, RemoteOK, Arbeitnow |
| ATS integrations | Greenhouse, Lever, Ashby |
| Optional aggregator | Jobicy |
| Testing | Python unittest |
| Version control | Git, GitHub |

## Architecture

The project uses independent adapters for each job source.

    Public job APIs ────────┐
                            │
    Greenhouse ─────────────┤
    Lever ──────────────────┤
    Ashby ──────────────────┤
                            ▼
                       Normalization
                            │
    Gmail alerts ───────────┤
                            ▼
                         Filters
                            │
                            ▼
                         Scoring
                            │
                            ▼
                      Deduplication
                            │
                            ▼
                       Telegram Bot
                            │
                            ▼
                    seen_jobs.json

Each source returns a normalized job structure, allowing the filtering and scoring system to process vacancies independently of their original platform.

A failure in one source does not stop the remaining sources from being processed.

## Project structure

    remote-job-bot/
    ├── config/
    │   └── job_boards.py       # ATS board configuration
    ├── data/
    │   └── seen_jobs.json      # Previously processed jobs
    ├── sources/
    │   ├── email_alerts.py     # Gmail job alert parser
    │   └── ...                 # Public API and ATS adapters
    ├── tests/                  # Automated tests
    ├── .github/
    │   └── workflows/
    │       └── jobs.yml        # Hourly GitHub Actions workflow
    ├── filters.py              # Filtering and scoring rules
    ├── telegram_bot.py         # Telegram integration
    ├── main.py                 # Main application workflow
    ├── requirements.txt
    └── README.md

## How it works

The bot follows a simple processing pipeline:

1. Fetch vacancies from all enabled sources.
2. Normalize jobs into a common structure.
3. Analyze location and remote compatibility.
4. Detect seniority and experience requirements.
5. Evaluate role and technology relevance.
6. Calculate a compatibility score.
7. Reject jobs below the configured threshold.
8. Check whether the vacancy was already processed.
9. Send new matching opportunities through Telegram.
10. Store the vacancy only after Telegram confirms delivery.

The current calibration uses:

    MIN_SCORE = 40

A job does not need to include `Junior` in its title. General roles can still qualify when their description indicates low experience requirements and sufficient compatibility.

## Getting started

### Requirements

Install:

- Python 3.12
- Git
- A Telegram account
- A Telegram Bot Token

### Installation

Clone the repository:

    git clone https://github.com/TU_USUARIO/remote-job-bot.git

Open the project:

    cd remote-job-bot

Create a virtual environment:

    py -3.12 -m venv .venv

Activate it in PowerShell:

    .\.venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

## Telegram configuration

Create a Telegram bot using `@BotFather` and obtain:

- Bot token
- Chat ID

Configure them as environment variables:

    $env:TELEGRAM_BOT_TOKEN = "your_token"
    $env:TELEGRAM_CHAT_ID = "your_chat_id"

Run the bot:

    python main.py

If no new matching jobs are found, no Telegram message is sent.

> Never commit Telegram tokens or other credentials to the repository.

## Gmail job alerts

The bot can also process job alerts forwarded to a dedicated Gmail account.

This allows alerts from platforms such as LinkedIn, Indeed, Glassdoor, Computrabajo and Wellfound to enter the same filtering pipeline used by public APIs.

The integration:

- Connects through IMAP with SSL
- Uses a Google App Password
- Opens the inbox in read-only mode
- Does not mark emails as read
- Does not delete or move messages
- Analyzes forwarded email content
- Extracts supported job links
- Ignores login, privacy, unsubscribe and preference links

Configure:

    $env:JOB_EMAIL_ADDRESS = "email@gmail.com"
    $env:JOB_EMAIL_APP_PASSWORD = "app-password"

The parser can inspect up to 100 messages from the previous five days.

## Public ATS boards

The bot supports public job board APIs from several Applicant Tracking Systems.

### Greenhouse

Uses:

    https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

Configure boards in `config/job_boards.py`:

    GREENHOUSE_BOARDS = [
        ("verified-token", "Company Name")
    ]

### Lever

Uses:

    https://api.lever.co/v0/postings/{site}?mode=json

Configuration:

    LEVER_COMPANIES = [
        ("verified-site", "Company Name")
    ]

European instances can use the `eu:` prefix.

### Ashby

Uses:

    https://api.ashbyhq.com/posting-api/job-board/{name}

Configuration:

    ASHBY_BOARDS = [
        ("verified-board", "Company Name")
    ]

ATS lists start empty so companies are only added after verifying that their job boards are relevant to the configured geographic criteria.

## Optional Jobicy integration

Jobicy can be enabled as an additional source without requiring an API key.

PowerShell:

    $env:ENABLE_JOBICY = "true"

For GitHub Actions, create the repository variable:

    ENABLE_JOBICY=true

The integration requests a maximum of 200 vacancies and is designed to respect the source's hourly request limit.

## GitHub Actions

The bot runs automatically through:

    .github/workflows/jobs.yml

The workflow supports:

- Hourly scheduled execution
- Manual execution with `workflow_dispatch`
- GitHub Secrets
- Persistence of processed job IDs

Create these repository secrets:

    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

If Gmail integration is enabled:

    JOB_EMAIL_ADDRESS
    JOB_EMAIL_APP_PASSWORD

The workflow runs at minute `0` of every hour in UTC.

When new vacancies are successfully delivered, the updated job history can be persisted with the commit:

    Update seen jobs

## Adding a new source

Create a new adapter inside `sources/` implementing:

    fetch_jobs() -> list[dict[str, str]]

Each normalized vacancy should provide:

    id
    title
    company
    location
    description
    url
    source
    published_at

Use an empty string when a field is unavailable.

Then register the adapter in:

    sources/__init__.py

Each source is isolated so an unavailable API or parsing error does not stop the complete job search.

## Testing

Run the automated test suite with:

    python -m unittest discover -s tests -v

Tests use simulated payloads and HTML instead of performing external requests.

Current test coverage includes:

- Job normalization
- Filtering
- Scoring
- Deduplication
- ATS payload processing
- Forwarded email parsing
- Failure tolerance

## Security

Sensitive information is kept outside the source code.

The project uses environment variables and GitHub Secrets for:

- Telegram Bot Token
- Telegram Chat ID
- Gmail address
- Gmail App Password

The public repository should never contain passwords, API tokens or private credentials.

## Current limitations

- Job availability depends on external public sources
- Public APIs can change their structure or availability
- Email extraction depends on the HTML structure of forwarded alerts
- ATS boards must be configured manually
- Geographic compatibility is determined from available job information
- Job scoring is heuristic and may occasionally include or exclude imperfect matches
- GitHub Actions scheduled workflows may not execute at the exact scheduled minute

## Roadmap

- [ ] Add additional public job sources
- [ ] Expand ATS company configuration
- [ ] Improve location detection
- [ ] Improve experience requirement extraction
- [ ] Add configurable job profiles
- [ ] Add technology preference weighting
- [ ] Improve email platform detection
- [ ] Add richer Telegram notifications
- [ ] Expand automated test coverage
- [ ] Add job statistics and execution summaries

## What I learned

This project helped me practice:

- Building automation tools with Python
- Consuming and normalizing multiple REST APIs
- Designing modular source adapters
- Implementing filtering and scoring algorithms
- Working with Telegram Bot API
- Processing email through IMAP
- Parsing forwarded HTML email alerts
- Integrating public ATS APIs
- Managing application state and deduplication
- Writing fault-tolerant integrations
- Creating automated workflows with GitHub Actions
- Managing secrets and environment variables
- Writing automated tests with Python

## Author

**Carlos Constantino**

- Portfolio: [portafoliofrann.netlify.app](https://portafoliofrann.netlify.app/)
- LinkedIn: [linkedin.com/in/fcoocarlos](https://www.linkedin.com/in/fcoocarlos/)
- GitHub: [github.com/frannnkkyy](https://github.com/frannnkkyy)

## Project status

Remote Job Bot is an active personal automation project designed to continuously monitor remote junior technology opportunities.

The project demonstrates API integration, automation, data filtering, email processing, testing and CI/CD workflows using Python and GitHub Actions.
