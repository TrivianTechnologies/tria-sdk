Historical failure witnesses, unchanged from the Open Rosetta private v3 review.
Target: TrivianTechnologies/tria-sdk @ 19919d8c2562cc00381b30ac3a303a83ce6787fa
SHA256 test_correction_gaps.py:
4e0eef1ec19732c6faeb37d6b99972cea11be001a30657b610e6970fdd0cd088

These four tests assert observed undesirable behavior. Passing them on the pinned
historical tree reproduces failures; it is not correction conformance. They are
outside current tests/ collection. Current positive/negative remediation tests are
tests/test_correction_safety.py. Run the frozen file using the original source tree
and pytest -c /dev/null so the current project's pythonpath setting cannot shadow
that source. Never revise these assertions to make a remediated kernel pass them.
