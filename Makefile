man: man/git-issue.ronn man/index.txt
	cd man && ronn --date=2017-12-21 --manual='git-issue manual' --organization='Kenneth Benzie' git-issue.ronn --style=toc
