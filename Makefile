## Convenience wrapper so users can simply run `make report` from the project
#  root.  All heavy-lifting (Python prep scripts + LaTeX build) lives in
#  writeup/Makefile; we just forward the chosen target.

.PHONY: report clean all

all: report

report:
	$(MAKE) -C writeup report

clean:
	$(MAKE) -C writeup clean
