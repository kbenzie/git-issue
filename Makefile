outputs = docs/git-issue.1 docs/index.html

all: $(outputs)

options = --date=2017-12-21 \
	  --manual='git-issue manual' \
	  --organization='Kenneth Benzie' \
	  --style=toc \
	  --pipe

docs/git-issue.1: docs/git-issue.ronn docs/index.txt
	cd docs && ronn -r $(options) git-issue.ronn > git-issue.1

docs/index.html: docs/git-issue.ronn docs/index.txt
	cd docs && ronn -5 $(options) git-issue.ronn > index.html

.PHONY: clean
clean:
	-rm $(outputs)
