#!/usr/bin/env python3
"""Central path helper: outputs are organized by REGISTER (slug) subfolders, so
adding hands (X4, X18, …) never crowds one flat directory. Slug derived from the
register name in dataset/pages.csv. Import from any script: `import paths`."""
import csv, re, functools

@functools.lru_cache(maxsize=1)
def _pid_register():
    return {r["page_id"]: r["register"]
            for r in csv.DictReader(open("dataset/pages.csv"))}

def slug(register: str) -> str:
    s = register.lower().replace("stato delle anime di ", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "misc"

def page_slug(pid: str) -> str:
    return slug(_pid_register()[pid])

# output path builders (register-scoped)
def cropped(pid):              return f"processed/cropped/{page_slug(pid)}/{pid}.jpg"
def cropped_dir(sl):           return f"processed/cropped/{sl}"
def transcription(pid, eng):   return f"processed/transcriptions/{page_slug(pid)}/{eng}/{pid}.txt"
def transcription_dir(sl, eng):return f"processed/transcriptions/{sl}/{eng}"
def translation(pid):          return f"processed/translations/{page_slug(pid)}/{pid}.txt"
def translation_dir(sl):       return f"processed/translations/{sl}"
def gold(pid):                 return f"gold/{page_slug(pid)}/{pid}"
def gold_dir(sl):              return f"gold/{sl}"
def model_dir(sl):             return f"gold/models/{sl}"
