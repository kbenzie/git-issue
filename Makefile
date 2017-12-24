outputs = docs/git-issue.1 docs/index.html

all: $(outputs)

options = --date=2017-12-21 \
	  --manual='git-issue manual' \
	  --organization='Kenneth Benzie' \
	  --style=toc \
	  --pipe

docs/git-issue.1: README.md index.txt
	ronn -r $(options) README.md > docs/git-issue.1

docs/index.html: README.md index.txt
	ronn -5 $(options) README.md > docs/index.html

.PHONY: clean
clean:
	-rm $(outputs)
