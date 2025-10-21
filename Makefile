.PHONY: mini-writeup mini-writeup-inputs mini-writeup-pdf

mini-writeup-inputs:
	$(MAKE) -C writeup mini-writeup-inputs

mini-writeup-pdf:
	$(MAKE) -C writeup mini-writeup-pdf

mini-writeup:
	$(MAKE) -C writeup mini-writeup
