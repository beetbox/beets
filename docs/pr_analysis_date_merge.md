\# PR Analysis: Fix inconsistent date metadata merging (PR #4199)



\## Overview



This document explains the date metadata merge fix in beets importer.



I noticed that earlier, beets handled year, month, and day separately. This caused inconsistent metadata updates. Sometimes year was updated but month and day were left old.



This created partial and incorrect date information in the music library.



This PR fixes that behavior by treating date fields as a single unit.



---



\## Problem



Earlier merge logic compared fields individually:



\- year

\- month

\- day



This caused issues like:



\- incomplete overwrite

\- valid data getting erased

\- inconsistent metadata state



This was happening inside importer merge logic.



---



\## Technical Changes



Modified files:



beets/importer.py  

Updated merge logic inside \_merge\_items function.



beets/library.py  

Improved attribute update handling.



test/test\_importer.py  

Added unit tests for date merge behavior.



Tests cover partial date scenarios.



---



\## Implementation



New logic checks:



\- if source metadata exists

\- if source date is more complete

\- if user has enabled keep current option



Only then overwrite happens.



Proper handling of None values is added.



This prevents valid date data from being lost.



---



\## Impact



Benefits:



\- More accurate metadata

\- Prevents silent corruption

\- Improves importer reliability



Risks:



\- Edge cases may still exist

\- Existing libraries may need re-import



---



\## Conclusion



This change improves metadata consistency and prevents data loss.



Treating date as a single unit makes importer behavior safer and predictable.



