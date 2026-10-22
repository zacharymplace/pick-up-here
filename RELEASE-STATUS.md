# 0.1.0-rc.7 — consolidated candidate

Application and tests are byte-identical to the previously packaged RC.7.
This consolidation removes superseded build notes, old demo media, and duplicate
submission drafts from the runnable app. Documentation is rewritten around the
current workflow. Application version and data formats are unchanged.

- 98 Python tests passed on the source candidate; repeated on this clean package.
- 62 browser checks passed on Linux Chrome; three use synthetic boundary responses.
- The refreshed RC.7 demo uses one real Gemma call, then the complete deterministic return flow on a synthetic repository. Its own status and raw response are separate from prior qualification.
- The historical seven-input live qualification was RC.1, with a preserved original 6/7 report and a corrected 7/7 assessment after a harness citation-check bug. It was not a clean all-green original run or a held-out evaluation.
- Physical Mac/current native-dialog acceptance, the prior empty limits bullet report, complete owner coffee-cad checkout acceptance, and fresh human usefulness are still open.
- Earlier human trials included generic/negative and partly-useful outcomes. No measured time-saving claim is made.

Operator-reported Mac acceptance subsequently passed the no-change workflow:
save brief, reload/reopen, collect and compare, export comparison, reload/reopen.
The app reported matching checksums and recomputed results. This does not add a
changed-file Mac test or fresh usefulness judgment. The empty identical-source
bullets in copied output remain unresolved as a possible display/copying issue.
The launcher encountered occupied ports; `python3 app.py --port 0 --open` worked.

This source and captioned demo are being published as RC.7. No stable release
promotion or DEV post submission is implied.
