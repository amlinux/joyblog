mg_deploy:
	cd /home/mg && rm -rf depl && find -name '*.pyc' -exec rm {} \; && bin/mg_compile . && cp -R mg depl/

deploy:
	make mg_deploy
	rm -rf depl
	find -name '*.pyc' -exec rm {} \;
	/home/mg/bin/mg_compile .
	mkdir -p depl/joyblog/bin
	mkdir depl/mg
	mv /home/mg/depl depl/mg/mg
	for m in director reload server worker scale ; do cp bin/mg_$$m depl/joyblog/bin/ ; done
	cp bin/*.sh depl/joyblog/bin/
	cp -R jb depl/joyblog
	mkdir depl/joyblog/static
	cp -R `ls -d static/* | grep -v storage` depl/joyblog/static/
	rm -rf depl/mg/mg/admin depl/mg/mg/constructor depl/mg/mg/data depl/mg/mg/mmo depl/mg/mg/socio `ls -d depl/mg/mg/templates/* | grep -v director` depl/mg/mg/test
	find depl \( -name '*.py' -or -name '.hg*' -or -name '*.po' -or -name '*.pot' \) -exec rm -rf {} \;
	rsync -r depl/* joyblog:/home/
	for server in Backend1 Backend2 DB1 DB2 ; do ssh joyblog "cd /home;rsync -r --exclude=storage mg joyblog $$server:/home/" ; done
	for server in Backend1 Backend2 ; do ssh joyblog "ssh $$server 'killall mg_worker'" ; done

cleanup:
	for server in DB1 DB2 ; do ssh joyblog "ssh $$server 'sudo /etc/init.d/cassandra stop'" ; done
	for server in DB1 DB2 ; do ssh joyblog "ssh $$server 'sudo rm -rf /var/lib/cassandra/data /var/lib/cassandra/commitlog'" ; done
	for server in Backend1 Backend2 ; do ssh joyblog "ssh $$server 'killall -KILL mg_worker mg_server'" ; done || true
	ssh joyblog "killall -KILL mg_director mg_server ; sudo /etc/init.d/memcached stop ; sudo killall -KILL memcached ; sudo /etc/init.d/memcached start" || true
	for server in DB1 DB2 ; do ssh joyblog "ssh $$server 'sudo /etc/init.d/cassandra start'" ; done
	ssh joyblog "sudo killall -HUP init ; sleep 3 ; sudo killall -HUP init" || true
	for server in Backend1 Backend2 ; do ssh joyblog "ssh $$server 'sudo killall -HUP init'" ; done || true
	ssh joyblog "sudo rm -rf /home/joyblog/static/storage/storage /var/log/syslog /var/log/user.log ; sudo /etc/init.d/rsyslog restart ; killall mg_director"
