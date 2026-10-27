#!/bin/bash
# Maintainer tool: macOS with Tableau Public installed only; not needed to build or view the workbook.
# Open the packaged workbook in Tableau Public, report errors from Tableau's own log,
# and save a screenshot of each Tableau window to tableau/screenshots/ (needs Screen Recording permission).
APP="Tableau Public (Apple silicon)"
LOG="$HOME/Documents/My Tableau Repository/Logs/log.txt"
DIR="$(cd "$(dirname "$0")" && pwd)"
WB="${WB:-$DIR/citibike_story.twbx}"
SHOTS="$DIR/screenshots"

osascript -e "quit app \"$APP\"" 2>/dev/null & sleep 5; pkill -x "Tableau Public" 2>/dev/null; sleep 2
START=$(date +"%Y-%m-%dT%H:%M:%S")
open -a "$APP" "$WB"
sleep "${WAIT:-30}"

python3 - "$LOG" "$START" "$(basename "$WB" .twbx)" <<'PY'
import json, re, sys, collections
errs, opened = collections.Counter(), False
for line in open(sys.argv[1], errors="ignore"):
    try: j = json.loads(line)
    except Exception: continue
    if j.get("ts", "")[:19] < sys.argv[2]: continue
    if j.get("k") == "detailed-error-msg":
        v = j["v"]
        for m in "\n".join(v.get("details", [])).split("\n"):
            if m.strip(): errs[re.sub(r"Error\(\d+,\d+\): ", "", m)] += 1
        if v.get("shortMessage"): errs[v["shortMessage"].replace("\n", " ")] += 1
    if j.get("k") == "msg" and "InvalidField" in str(j.get("v")):  # makes a sheet render blank
        errs[re.sub(r"\[federated\.\w+\]\.", "", str(j["v"]))] += 1
    if sys.argv[3] in json.dumps(j.get("v")): opened = True
print("workbook seen in log:", opened)
print("ERRORS:" if errs else "No errors in log.")
for m, c in errs.most_common(): print(f"  {c} x {m[:300]}")
PY

mkdir -p "$SHOTS"
osascript -l JavaScript -e '
ObjC.import("CoreGraphics");
var list = ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionAll, 0)), out = [];
for (var i = 0; i < list.count; i++) { var w = list.objectAtIndex(i);
  var owner = ObjC.unwrap(w.objectForKey("kCGWindowOwnerName")), name = ObjC.unwrap(w.objectForKey("kCGWindowName"));
  var b = w.objectForKey("kCGWindowBounds");
  if (owner && owner.indexOf("Tableau") >= 0 && name && ObjC.unwrap(b.objectForKey("Height")) > 100)
    out.push(ObjC.unwrap(w.objectForKey("kCGWindowNumber")) + "\t" + name); }
out.join("\n");' | while IFS=$'\t' read -r id name; do
  echo "window $id: $name"
  [ "$name" = "Warning" ] && echo "WARNING DIALOG open (a sheet was rejected; see $SHOTS/window_$id.png)"
  screencapture -x -o -l "$id" "$SHOTS/window_$id.png"
done
