%global debug_package %{nil}

Name:           elasticsearch
Version:        1.5.1
Release:        1%{?dist}
Summary:        Search & Analyze in Real Time

Group:          Applications/System
License:        Apache 2.0
URL:            https://www.elastic.co/downloads/elasticsearch
Source0:        https://github.com/elastic/elasticsearch/archive/v%{version}/%{name}-%{version}.tar.gz
Source1:        %{name}.logrotate
Source2:        %{name}.service
Source3:        %{name}.sysconf
Source4:        %{name}.tmpfile

%if 0%{?fedora} >= 18 || 0%{?rhel} >= 7
BuildRequires:  systemd
%endif
BuildRequires:  maven
Requires:  java-1.8.0-openjdk

%description
Elasticsearch is a distributed, open source search and analytics engine,
designed for horizontal scalability, reliability, and easy management.

%prep
%setup -q

%build
mvn clean package -DskipTests --threads 2.0C --errors
tar xf target/releases/%{name}-%{version}.tar.gz

%check
SMP="%{?_smp_mflags}"
mvn test -Dtests.jvms=${SMP/-j} -Dtests.class="org.elasticsearch.package.*"

%install
install -d %{buildroot}%{_sharedstatedir}/%{name} \
           %{buildroot}%{_var}/run/%{name} \
           %{buildroot}%{_var}/log/%{name} \
           %{buildroot}%{_bindir}

# /etc
%if 0%{?rhel} < 7
install -Dm 644 src/rpm/init.d/%{name} %{buildroot}%{_initddir}/%{name}
%endif
install -Dm 644 %{SOURCE1} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}
install -Dm 644 %{SOURCE3} %{buildroot}%{_sysconfdir}/sysconfig/%{name}
install -d %{buildroot}%{_sysconfdir}/%{name}
cp config/* %{buildroot}%{_sysconfdir}/%{name}

# /usr
%if 0%{?fedora} >= 18 || 0%{?rhel} >= 7
install -Dm 644 %{SOURCE2} %{buildroot}%{_unitdir}/%{name}.service
install -Dm 644 %{SOURCE4} %{buildroot}%{_tmpfilesdir}/%{name}.conf
install -Dm 644 src/rpm/systemd/sysctl.d/%{name}.conf %{buildroot}%{_sysctldir}/%{name}.conf
%endif
pushd %{name}-%{version}
install -d %{buildroot}%{_datadir}/%{name}/bin
install -m 755 bin/{%{name},%{name}.in.sh,plugin} %{buildroot}%{_datadir}/%{name}/bin/
sed -i '/ES_HOME/s|.dirname.*|/usr/lib/%{name}|' \
       %{buildroot}%{_datadir}/%{name}/bin/{%{name},plugin}
ln -sf %{_datadir}/%{name}/bin/plugin %{buildroot}%{_bindir}/%{name}-plugin

# /usr/lib
install -d %{buildroot}%{_prefix}/lib/%{name}/lib
cp -r lib %{buildroot}%{_prefix}/lib/%{name}/
rm -rf %{buildroot}%{_prefix}/lib/%{name}/lib/sigar/*{freebsd,solaris,macosx,winnt}*

%clean
rm -rf $RPM_BUILD_ROOT

%pre
# create group
getent group %{name} >/dev/null || groupadd -r %{name}

# create user
getent passwd %{name} >/dev/null || \
  useradd -r -g %{name} -d %{_datadir}/%{name} -s /sbin/nologin \
          -c "%{name} user" %{name}

%preun
[ -f /etc/sysconfig/elasticsearch ] && . /etc/sysconfig/elasticsearch

stopElasticsearch() {
	if [ -x /bin/systemctl ] ; then
		/bin/systemctl stop elasticsearch.service > /dev/null 2>&1 || :
	elif [ -x /etc/init.d/elasticsearch ] ; then
		/etc/init.d/elasticsearch stop
	elif [ -x /etc/rc.d/init.d/elasticsearch ] ; then
		/etc/rc.d/init.d/elasticsearch stop
	fi
}

# Removal: $1 == 0
# Dont do anything on upgrade, because the preun script in redhat gets executed after the postinst (madness!)
if [ $1 -eq 0 ] ; then
    stopElasticsearch

    if [ -x /bin/systemctl ] ; then
        /bin/systemctl --no-reload disable elasticsearch.service > /dev/null 2>&1 || :
    fi
    if [ -x /sbin/chkconfig ] ; then
        /sbin/chkconfig --del elasticsearch 2> /dev/null
    fi
fi

%post
[ -f /etc/sysconfig/elasticsearch ] && . /etc/sysconfig/elasticsearch

# Generate ES plugin directory and hand over ownership to ES user
mkdir -p /usr/lib/elasticsearch/plugins
chown elasticsearch:elasticsearch /usr/lib/elasticsearch/plugins

startElasticsearch() {
	if [ -x /bin/systemctl ] ; then
		/bin/systemctl start elasticsearch.service
	elif [ -x /etc/init.d/elasticsearch ] ; then
		/etc/init.d/elasticsearch start
	# older suse linux distributions do not ship with systemd
	# but do not have an /etc/init.d/ directory
	# this tries to start elasticsearch on these as well without failing this script
	elif [ -x /etc/rc.d/init.d/elasticsearch ] ; then
		/etc/rc.d/init.d/elasticsearch start
	fi
}

stopElasticsearch() {
	if [ -x /bin/systemctl ] ; then
		/bin/systemctl stop elasticsearch.service > /dev/null 2>&1 || :
	elif [ -x /etc/init.d/elasticsearch ] ; then
		/etc/init.d/elasticsearch stop
	elif [ -x /etc/rc.d/init.d/elasticsearch ] ; then
		/etc/rc.d/init.d/elasticsearch stop
	fi
}

# Initial installation: $1 == 1
# Upgrade: $1 == 2, and configured to restart on upgrade
if [ $1 -eq 1 ] ; then

    if [ -x /bin/systemctl ] ; then
        /bin/systemctl daemon-reload
        
    elif [ -x /sbin/chkconfig ] ; then
        /sbin/chkconfig --add elasticsearch
    fi

elif [ $1 -ge 2 -a "$RESTART_ON_UPGRADE" == "true" ] ; then
	stopElasticsearch
	startElasticsearch
fi

%postun
# only execute in case of package removal, not on upgrade
if [ $1 -eq 0 ] ; then

    getent passwd elasticsearch > /dev/null
    if [ "$?" == "0" ] ; then
        userdel elasticsearch
    fi

    getent group elasticsearch >/dev/null
    if [ "$?" == "0" ] ; then
        groupdel elasticsearch
    fi

    # Remove plugin directory and all plugins
    rm -rf /usr/lib/elasticsearch/plugins
fi

%files
%defattr(-,root,root,-)
%if 0%{?rhel} < 7
%{_initddir}/%{name}
%endif
%{_sysconfdir}/logrotate.d/%{name}
%{_sysconfdir}/sysconfig/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/*.yml

%if 0%{?fedora} >= 18 || 0%{?rhel} >= 7
%{_tmpfilesdir}/%{name}.conf
%{_sysctldir}/%{name}.conf
%{_unitdir}/%{name}.service
%endif
%{_bindir}/%{name}*
%{_datadir}/%{name}
%{_prefix}/lib/%{name}

%defattr(-,%{name},%{name},-)
%{_sharedstatedir}/%{name}
%{_var}/run/%{name}
%{_var}/log/%{name}

%changelog
* Fri Apr 10 2015 mosquito <sensor.wen@gmail.com> - 1.5.1-1
- update version to 1.5.1

* Thu Apr  2 2015 mosquito <sensor.wen@gmail.com> - 1.5.0-1
- initial built
