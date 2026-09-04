"""Candidate-focused scoring for remote junior technology and marketing jobs."""
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

MIN_SCORE = 40
REMOTE_SOURCES = {"remotive", "remoteok"}
REMOTE_TERMS = ("remote", "fully remote", "100% remote", "work from home", "work from anywhere", "home office", "worldwide", "global remote", "distributed team", "anywhere")
MEXICO_REGIONS = ("mexico", "méxico", "latam", "latin america", "americas", "north america", "worldwide", "anywhere")
GLOBAL_EVIDENCE_RE = re.compile(r"\b(?:candidates? (?:accepted )?worldwide|worldwide candidates?|work from anywhere|anywhere in the world|open to candidates globally|global remote|remote worldwide)\b", re.I)
EXPLICIT_GEO_RE = re.compile(r"\b(?:(?:us|u\.s\.|usa|united states|canada|uk|united kingdom|europe|eu) only|(?:us|u\.s\.) (?:residents|citizens) only|must (?:reside|live|be based|be located) in (?:the )?(?:us|u\.s\.|usa|united states))\b", re.I)
ONSITE_LOCATION_RE = re.compile(r"\b(?:hybrid|híbrido|hibrido|on[ -]?site|presencial|office[ -]based|in[ -]office|relocation required)\b", re.I)
MANDATORY_ONSITE_RE = re.compile(r"\b(?:this (?:role|position|job) is|must|required to|requires?|work arrangement:?)\b.{0,45}\b(?:hybrid|on[ -]?site|in[ -]?office|office[ -]?based|presencial|relocat(?:e|ion))\b", re.I)
SENIOR_TITLE_RE = re.compile(r"\b(?:senior|sr\.?|staff|principal|director|head|vice president|vp|engineering manager|tech lead|team lead|lead (?:engineer|developer|architect))\b", re.I)

ENTRY_TERMS = ("junior", "entry level", "entry-level", "trainee", "intern", "internship", "associate", "graduate", "new grad", "recent graduate", "early career", "engineer i", "developer i", "specialist i", "level 1", "tier 1", "l1")
NO_EXPERIENCE_TERMS = ("no experience", "no previous experience", "no prior experience", "0 years", "0-1 years", "0–1 years", "0 to 1 years")
LOW_EXPERIENCE_TERMS = ("0-2 years", "0–2 years", "0 to 2 years", "1 year", "1-2 years", "1–2 years", "1 to 2 years", "up to 2 years")
PROJECT_TERMS = ("personal projects", "academic projects", "school projects", "internship experience", "equivalent experience")
RECENT_GRAD_TERMS = ("recent graduate", "new grad", "fresh graduate", "graduates welcome")
TRAINING_TERMS = ("training provided", "full training", "on-the-job training", "on the job training")

DEV_ROLES = ("software developer", "software engineer", "frontend", "front end", "web developer", "javascript developer", "react developer", "full stack", "fullstack", "application developer", "product engineer", "ai engineer")
IT_ROLES = ("it support", "technical support", "help desk", "helpdesk", "service desk", "application support", "support specialist", "support representative", "support engineer", "product support", "saas support", "qa tester", "manual qa", "junior qa", "qa engineer", "software tester", "quality assurance", "implementation specialist", "implementation engineer", "onboarding specialist", "it analyst", "application analyst")
MEDIUM_ROLES = ("systems analyst", "system analyst", "business analyst", "technical operations", "technical consultant", "data analyst", "operations analyst", "customer support")
MARKETING_ROLES = ("marketing assistant", "digital marketing assistant", "marketing coordinator", "marketing intern", "social media assistant", "social media coordinator", "community manager", "content assistant", "content coordinator", "content specialist", "seo assistant", "junior seo", "crm assistant", "e-commerce assistant", "ecommerce assistant", "marketing operations assistant", "copywriter", "content writer", "marketing specialist")

TECHNOLOGIES = (
    ("JavaScript", ("javascript",)), ("TypeScript", ("typescript",)), ("React Native", ("react native",)), ("React", ("react",)), ("Expo", ("expo",)), ("Node.js", ("node.js", "nodejs")),
    ("HTML", ("html",)), ("CSS", ("css",)), ("SQL", ("sql",)), ("MySQL", ("mysql",)), ("SQL Server", ("sql server",)), ("Supabase", ("supabase",)), ("Firebase", ("firebase",)),
    ("GitHub", ("github",)), ("Git", ("git",)), ("ServiceNow", ("servicenow",)), ("Microsoft 365", ("microsoft 365", "office 365")), ("Azure", ("azure",)),
    ("REST APIs", ("rest api", "restful api")), ("PWA", ("pwa", "progressive web app")), ("Docker", ("docker",)), ("Figma", ("figma",)),
)
MARKETING_SKILLS = (
    ("Canva", ("canva",)), ("Figma", ("figma",)), ("Google Analytics", ("google analytics", "ga4")), ("SEO", ("seo",)), ("SEM", ("sem",)),
    ("Google Ads", ("google ads",)), ("Meta Ads", ("meta ads", "facebook ads")), ("Social Media", ("social media", "instagram", "tiktok")),
    ("Content", ("content creation", "copywriting")), ("Email Marketing", ("email marketing",)), ("CRM", ("crm", "hubspot")),
    ("WordPress", ("wordpress",)), ("Analytics", ("analytics",)), ("E-commerce", ("ecommerce", "e-commerce")),
)

@dataclass(frozen=True)
class JobAssessment:
    score: int
    category: str
    reasons: list[str]
    weaknesses: list[str]
    rejection: str = ""
    skills: list[str] | None = None
    experience: str = ""
    role_group: str = ""

class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.parts: list[str] = []
    def handle_data(self, data: str) -> None:
        self.parts.append(data)

def clean_html(value: Any) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(str(value or ""))); value = " ".join(parser.parts)
    except Exception:
        value = str(value or "")
    return re.sub(r"\s+", " ", value).strip()

def _has(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I) for term in terms)

def _matches(text: str, vocabulary: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    return [label for label, aliases in vocabulary if _has(text, aliases)]

def _role_group(title: str, description: str) -> tuple[str, int]:
    if _has(title, DEV_ROLES): return "development", 25
    if _has(title, IT_ROLES): return "it/support/qa", 25
    if _has(title, MARKETING_ROLES): return "marketing", 12
    if _has(title, MEDIUM_ROLES) and _has(f"{title} {description}", ENTRY_TERMS): return "technical/operations", 16
    return "", 0

def _specific_remote_location(location: str) -> bool:
    """Detect a remote label tied to a place not known to include Mexico."""
    value = location.strip().lower()
    if not value or value in {"remote", "fully remote", "100% remote", "worldwide", "anywhere"}:
        return False
    if _has(value, MEXICO_REGIONS):
        return False
    if value.startswith("remote") or "remote -" in value:
        return True
    # Remote-oriented feeds sometimes omit the word Remote but give a city/country.
    return True

def _experience(description: str) -> tuple[int, str, list[str], bool]:
    """Score candidate experience, separating preferred, required and incidental text."""
    if _has(description, NO_EXPERIENCE_TERMS): return 20, "No experience / 0-1 years", [], False
    if _has(description, LOW_EXPERIENCE_TERMS): return 15, "0-2 years", [], False
    if re.search(r"\b2\s*\+\s*years?\b.{0,45}\bpreferred\b|\bpreferred\b.{0,45}\b2\s*\+\s*years?", description, re.I):
        return 5, "2+ years preferred", ["2+ años preferidos"], True
    if re.search(r"\b3\s*\+?\s*years?\b.{0,45}\bpreferred\b|\bpreferred\b.{0,45}\b3\s*\+?\s*years?", description, re.I):
        return -5, "3 years preferred", ["Solicita 3 años como preferencia"], True

    explicit_required = [int(value) for value in re.findall(r"\b([2-9]|1\d)\s*\+?\s*years?\b.{0,45}\b(?:required|minimum|mandatory)\b", description, re.I)]
    requirement_context = " ".join(re.findall(r"(?:requirements?|qualifications?|what you need|must have|required experience)(.{0,900})", description, re.I))
    direct_required = " ".join(re.findall(r"(?:required|minimum of|must have|you have|you bring|requires?).{0,100}", description, re.I))
    candidate_context = f"{requirement_context} {direct_required}"
    years = explicit_required + [int(value) for value in re.findall(r"\b([2-9]|1\d)\s*\+?\s*years?\b", candidate_context, re.I)]
    if years and max(years) >= 4: return -50, f"{max(years)}+ years required", [f"Requiere {max(years)}+ años"], True
    if years and max(years) == 3: return -25, "3+ years required", ["Requiere 3+ años"], True
    if years and max(years) == 2: return -5, "2 years required", ["Requiere 2 años"], True
    # A bare years phrase outside candidate requirement context is incidental.
    return 0, "", [], False

def assess_job(job: dict[str, Any]) -> JobAssessment:
    """Assess whether this job is worth applying to for the configured candidate."""
    title = clean_html(job.get("title")).lower(); location = clean_html(job.get("location")).lower()
    description = clean_html(job.get("description")).lower(); source = clean_html(job.get("source")).lower()
    tags = " ".join(str(tag) for tag in (job.get("tags") or [])); full_text = f"{title} {description} {tags}".lower()
    if ONSITE_LOCATION_RE.search(f"{title} {location}") or MANDATORY_ONSITE_RE.search(description):
        return JobAssessment(0, "REJECT", [], [], "hybrid/onsite")
    remote_flag = job.get("remote")
    if remote_flag is False:
        return JobAssessment(0, "REJECT", [], [], "not remote")
    global_evidence = bool(GLOBAL_EVIDENCE_RE.search(f"{location} {description}")) or _has(location, MEXICO_REGIONS)
    if (EXPLICIT_GEO_RE.search(f"{location} {description}") or _specific_remote_location(location)) and not global_evidence:
        return JobAssessment(0, "REJECT", [], [], "geo restriction")
    if SENIOR_TITLE_RE.search(title):
        return JobAssessment(0, "REJECT", [], [], "senior")
    if not (remote_flag is True or source in REMOTE_SOURCES or _has(f"{location} {description}", REMOTE_TERMS)):
        return JobAssessment(0, "REJECT", [], [], "not remote")
    role_group, role_points = _role_group(title, description)
    if not role_group:
        return JobAssessment(0, "REJECT", [], [], "irrelevant role")

    score = 15 + role_points; reasons = ["Remoto desde México", f"Rol {role_group} compatible"]
    entry = _has(f"{title} {description}", ENTRY_TERMS)
    if entry: score += 20; reasons.append("Junior / entry level")
    exp_points, experience, weaknesses, stretch = _experience(description)
    score += exp_points
    if experience and exp_points > 0: reasons.append(experience)
    if _has(description, PROJECT_TERMS): score += 10; reasons.append("Acepta proyectos/prácticas/equivalencia")
    if _has(description, RECENT_GRAD_TERMS): score += 10; reasons.append("Acepta recién egresados")
    if _has(description, TRAINING_TERMS): score += 10; reasons.append("Ofrece capacitación")

    tech = _matches(full_text, TECHNOLOGIES)
    if role_group == "development":
        preferred = [skill for skill in tech if skill in {"JavaScript", "TypeScript", "React", "React Native", "Expo", "Node.js", "HTML", "CSS", "SQL", "MySQL", "SQL Server", "Supabase", "Firebase", "Git", "GitHub", "REST APIs", "PWA", "Docker", "Azure"}]
        score += min(20, len(preferred) * 4); skills = preferred[:5]
    elif role_group == "it/support/qa":
        support = [skill for skill in tech if skill in {"ServiceNow", "Microsoft 365", "Azure", "SQL", "REST APIs", "Git"}]
        score += min(20, sum(10 if skill in {"ServiceNow", "Microsoft 365"} else 4 for skill in support)); skills = support[:5]
    else:
        score += min(8, len(tech) * 2); skills = tech[:4]
    if skills: reasons.append("Stack: " + ", ".join(skills))
    if role_group == "marketing":
        marketing = _matches(full_text, MARKETING_SKILLS); score += min(10, len(marketing) * 3)
        skills = list(dict.fromkeys(skills + marketing[:4]));
        if marketing: reasons.append("Marketing: " + ", ".join(marketing[:3]))

    score = max(0, min(100, score))
    if exp_points <= -50: category = "REJECT"
    elif score >= 80 and not stretch: category = "EXCELLENT"
    elif stretch and score >= MIN_SCORE: category = "STRETCH"
    elif score >= MIN_SCORE: category = "GOOD"
    else: category = "REJECT"
    rejection = "experience" if exp_points <= -50 else ("below score" if category == "REJECT" else "")
    return JobAssessment(score, category, reasons, weaknesses, rejection, skills, experience, role_group)

def evaluate_job(job: dict[str, Any]) -> tuple[int, list[str], str]:
    """Backward-compatible scoring API."""
    result = assess_job(job)
    return result.score, result.reasons, result.rejection

def calculate_score(job: dict[str, Any]) -> tuple[int, list[str]]:
    result = assess_job(job)
    return result.score, result.reasons
