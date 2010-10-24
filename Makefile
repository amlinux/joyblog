mg_deploy:
	cd /home/mg && rm -rf depl && find -name '*.pyc' -exec rm {} \; && bin/mg_compile . && cp -R mg depl/

deploy:
	make mg_deploy
	rm -rf depl
	find -name '*.pyc' -exec rm {} \;
	/home/mg/bin/mg_compile .
	mkdir -p depl/joyblog/bin
	mv /home/mg/depl depl/mg
	for m in director reload server worker ; do cp bin/mg_$$m depl/joyblog/bin/ ; done
	cp -R jb static depl/joyblog
	rm -rf depl/mg/admin depl/mg/constructor depl/mg/data depl/mg/locale depl/mg/mmo depl/mg/socio depl/mg/templates depl/mg/test
	find depl \( -name '*.py' -or -name '.hg*' -or -name '*.po' -or -name '*.pot' \) -exec rm -rf {} \;
	rsync -r depl/* joyblog:/home/
	ssh joyblog 'cd /home;rsync -r mg joyblog Backend1:/home/'
