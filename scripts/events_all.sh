#!/bin/bash
# per-state events from the national Mobilize snapshot (+ Wikipedia debate tables for PA)
for st in $(python3 -c "import sys;sys.path.insert(0,'scripts');from states_meta import STATES;print(' '.join(s for s,_,_ in STATES))"); do
  STATE=$st SEATS=v2/states/$st/seats.json EVOUT=v2/states/$st/events.json python3 scripts/fetch_events.py | head -1
done
