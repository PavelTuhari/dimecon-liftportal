import glob, re
n = 0
for p in glob.glob("portal/templates/**/*.html", recursive=True):
    s = open(p, encoding="utf-8").read()
    s2 = re.sub(r'(\{% from "_macros\.html" import [^%]*?)(?<! with context) %\}', r"\1 with context %}", s)
    if s2 != s:
        open(p, "w", encoding="utf-8").write(s2); n += 1
print("patched", n)
