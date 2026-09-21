import os


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Go cry kid mi-mi-mi!
src_file = os.path.join(project_root, "dataset", "astra_voice", "monolog.txt")
dst_file = os.path.join(project_root, "dataset", "astra_voice", "metadata.csv")

with open(src_file, "r", encoding="utf-8") as f:
    text = f.read()

phrases = text.split("|")

lines = []
for p in phrases:
    clean = " ".join(p.split())
    if clean:
        lines.append(clean)

with open(dst_file, "w", encoding="utf-8") as f:
    for i, phrase in enumerate(lines, start=1):
        f.write(f"{i:03d}|{phrase}\n")

print(f"Done. Lines recorded: {len(lines)}")