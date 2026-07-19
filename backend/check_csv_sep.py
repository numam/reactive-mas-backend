"""Check all CSV files in output_3mode root for separator issues."""
import os

OUTPUT_HITL = r"d:\PAPER\Multi Agent (NUS)\supply-chain\code\hitl\output_3mode"

for fname in os.listdir(OUTPUT_HITL):
    if not fname.endswith(".csv"):
        continue
    fpath = os.path.join(OUTPUT_HITL, fname)
    if not os.path.isfile(fpath):
        continue
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline()
    commas = header.count(",")
    semis  = header.count(";")
    sep = "SEMICOLON" if semis > commas else "COMMA"
    flag = " *** WRONG SEP ***" if sep == "SEMICOLON" else ""
    print(f"{fname:45s}  sep={sep}  (commas={commas}, semis={semis}){flag}")
