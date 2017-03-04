
%global release_version 2
%global _moduledir /%{_lib}/security
%global _ovirt_version 1.0.13

# Note this is not building any package
# There exists no ovirt-guest-agent package
Name: ovirt-guest-agent
Version: 1.0.13
Release: %{release_version}%{?dist}
Summary: The oVirt Guest Agent
Group: Applications/System
License: ASL 2.0
URL: http://wiki.ovirt.org/wiki/Category:Ovirt_guest_agent
Source0: http://evilissimo.fedorapeople.org/releases/ovirt-guest-agent/%{version}/%{name}-%{_ovirt_version}.tar.bz2
BuildRequires: libtool
BuildRequires: pam-devel
BuildRequires: python2-devel
BuildRequires: python-pep8
BuildRequires: udev
%if 0%{?fedora} >= 18
BuildRequires: systemd
%else
BuildRequires: systemd-units
%endif
Requires: %{name}-common = %{version}-%{release}

# The ovirt-guest-agent main package is empty.
# This has been done to avoid content duplication. The common package provides
# the content for the main package to work around the issue with the other
# subpackages. You cannot have a noarch main package and arch specific
# subpackages.
%package common
Summary: Commonly used files of the oVirt Guest Agent
BuildArch: noarch
Requires: dbus-python
Requires: pygobject2
Requires: rpm-python
Requires: python-ethtool >= 0.4-1
Requires: udev >= 095-14.23
Requires: kernel > 2.6.18-238.5.0
Requires: usermode
%if 0%{?fedora} >= 18
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%endif
Provides: %{name} = %{version}-%{release}

# If selinux is installed and has a version lower than tested, our package
# would not work as expected.
%if 0%{?fc16}
Conflicts: selinux-policy < 3.10.0-77
%endif
%if 0%{?fedora} >= 17
Conflicts: selinux-policy < 3.10.0-89
%endif

%package pam-module
Summary: PAM module for the oVirt Guest Agent
Requires: %{name} = %{version}-%{release}
Requires: pam

%package kdm-plugin
Summary: KDM plug-in for the oVirt Guest Agent
BuildRequires: kdebase-workspace-devel
BuildRequires: gcc-c++
Requires: %{name} = %{version}-%{release}
Requires: %{name}-pam-module = %{version}-%{release}
Requires: kdm

%if 0%{?fedora} >= 20
%package gdm-plugin
Summary: Files for the GDM plug-in of the oVirt Guest Agent
BuildArch: noarch
Requires: %{name} = %{version}-%{release}
Requires: %{name}-pam-module = %{version}-%{release}
Requires: gdm
Requires: gnome-shell

%description gdm-plugin
Files required for the GDM extension to use the oVirt automatic log-in
system
%endif

%description
This is the oVirt management agent running inside the guest. The agent
interfaces with the oVirt manager, supplying heart-beat info as well as
run-time data from within the guest itself. The agent also accepts
control commands to be run executed within the OS (like: shutdown and
restart).

%description common
This is the oVirt management agent running inside the guest. The agent
interfaces with the oVirt manager, supplying heart-beat info as well as
run-time data from within the guest itself. The agent also accepts
control commands to be run executed within the OS (like: shutdown and
restart).

%description pam-module
The oVirt PAM module provides the functionality necessary to use the
oVirt automatic log-in system.

%description kdm-plugin
The KDM plug-in provides the functionality necessary to use the
oVirt automatic log-in system.

%prep
%setup -q -n ovirt-guest-agent-%{_ovirt_version}

%build
%configure \
    --enable-securedir=%{_moduledir} \
    --includedir=%{_includedir}/security \
    --without-gdm \
    --with-pam-prefix=%{_sysconfdir}

make %{?_smp_mflags}

%install
make install DESTDIR=%{buildroot}
cp gdm-plugin/gdm-ovirtcred.pam %{buildroot}/%{_sysconfdir}/pam.d/gdm-ovirtcred
mkdir -p %{buildroot}%{_udevrulesdir}
mv %{buildroot}%{_sysconfdir}/udev/rules.d/55-ovirt-guest-agent.rules %{buildroot}%{_udevrulesdir}/55-ovirt-guest-agent.rules
sed '1{\@^#!/usr/bin/env python@d}' %{buildroot}%{_datadir}/ovirt-guest-agent/timezone.py > %{buildroot}%{_datadir}/ovirt-guest-agent/timezone.py.new
mv %{buildroot}%{_datadir}/ovirt-guest-agent/timezone.py{.new,}

# Ensure we're elevating the guest agent diskmapper tool
# This is done by replacing the original with a symlink to consolehelper
# and renaming the original before hand to diskmapper.script
# Then we install the necessary console.apps script which points to the renamed
# original and also copy the necessary pam configuration
cp %{buildroot}%{_sysconfdir}/security/console.apps/{ovirt-logout,diskmapper}
cp %{buildroot}%{_sysconfdir}/pam.d/{ovirt-logout,diskmapper}
sed -i "s/LogoutActiveUser.py/diskmapper.script/g" %{buildroot}%{_sysconfdir}/security/console.apps/diskmapper
mv %{buildroot}%{_datadir}/ovirt-guest-agent/diskmapper{,.script}
ln -sf /usr/bin/consolehelper %{buildroot}%{_datadir}/ovirt-guest-agent/diskmapper


%pre common
getent group ovirtagent >/dev/null || groupadd -r -g 175 ovirtagent
getent passwd ovirtagent > /dev/null || \
    /usr/sbin/useradd -u 175 -g 175 -o -r ovirtagent \
    -c "oVirt Guest Agent" -d %{_datadir}/ovirt-guest-agent -s /sbin/nologin
exit 0

%post common
/sbin/udevadm trigger --subsystem-match="virtio-ports" \
    --attr-match="name=com.redhat.rhevm.vdsm"
/sbin/udevadm trigger --subsystem-match="virtio-ports" \
    --attr-match="name=ovirt-guest-agent.0"

%if 0%{?fedora} < 18
    /bin/systemctl daemon-reload
%else
    # New macro for F18+
    %systemd_post ovirt-guest-agent.service
%endif

%preun common
if [ "$1" -eq 0 ]
then
    %if 0%{?fedora} < 18
        /bin/systemctl stop ovirt-guest-agent.service > /dev/null 2>&1
    %else
        # New macro for F18+
        %systemd_preun ovirt-guest-agent.service
    %endif

    # non blocking uninstalled notification
    echo -e '{"__name__": "uninstalled"}\n' | dd \
        of=/dev/virtio-ports/com.redhat.rhevm.vdsm \
        oflag=nonblock status=noxfer conv=nocreat 1>& /dev/null || :

    echo -e '{"__name__": "uninstalled"}\n' | dd \
        of=/dev/virtio-ports/org.ovirt.vdsm \
        oflag=nonblock status=noxfer conv=nocreat 1>& /dev/null || :
fi

%postun common
if [ "$1" -eq 0 ]
then
    %if 0%{?fedora} < 17
        /bin/systemctl daemon-reload
    %endif

    # Let udev clear access rights
    /sbin/udevadm trigger --subsystem-match="virtio-ports" \
        --attr-match="name=com.redhat.rhevm.vdsm"
    /sbin/udevadm trigger --subsystem-match="virtio-ports" \
        --attr-match="name=ovirt-guest-agent.0"
fi

%if 0%{?fedora} < 18
    if [ "$1" -ge 1 ]; then
        /bin/systemctl try-restart ovirt-guest-agent.service >/dev/null 2>&1 || :
    fi
%else
    # New macro for F18+
    %systemd_postun_with_restart ovirt-guest-agent.service
%endif

%files common
%dir %attr (755,ovirtagent,ovirtagent) %{_localstatedir}/log/ovirt-guest-agent
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent

# Hook configuration directories
%dir %attr (755,root,root) %{_sysconfdir}/ovirt-guest-agent
%dir %attr (755,root,root) %{_sysconfdir}/ovirt-guest-agent/hooks.d
%dir %attr (755,root,root) %{_sysconfdir}/ovirt-guest-agent/hooks.d/before_migration
%dir %attr (755,root,root) %{_sysconfdir}/ovirt-guest-agent/hooks.d/after_migration
%dir %attr (755,root,root) %{_sysconfdir}/ovirt-guest-agent/hooks.d/before_hibernation
%dir %attr (755,root,root) %{_sysconfdir}/ovirt-guest-agent/hooks.d/after_hibernation

# Hook installation directories
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/defaults
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/before_migration
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/after_migration
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/before_hibernation
%dir %attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/after_hibernation

%config(noreplace) %{_sysconfdir}/ovirt-guest-agent.conf

%doc AUTHORS COPYING NEWS README

%config(noreplace) %{_sysconfdir}/pam.d/ovirt-logout
%config(noreplace) %{_sysconfdir}/pam.d/ovirt-locksession
%config(noreplace) %{_sysconfdir}/pam.d/ovirt-container-list
%config(noreplace) %{_sysconfdir}/pam.d/ovirt-shutdown
%config(noreplace) %{_sysconfdir}/pam.d/ovirt-hibernate
%config(noreplace) %{_sysconfdir}/pam.d/ovirt-flush-caches
%config(noreplace) %{_sysconfdir}/pam.d/diskmapper
%config(noreplace) %attr(644,root,root) %{_udevrulesdir}/55-ovirt-guest-agent.rules
%config(noreplace) %{_sysconfdir}/dbus-1/system.d/org.ovirt.vdsm.Credentials.conf
%config(noreplace) %{_sysconfdir}/security/console.apps/ovirt-logout
%config(noreplace) %{_sysconfdir}/security/console.apps/ovirt-locksession
%config(noreplace) %{_sysconfdir}/security/console.apps/ovirt-container-list
%config(noreplace) %{_sysconfdir}/security/console.apps/ovirt-shutdown
%config(noreplace) %{_sysconfdir}/security/console.apps/ovirt-hibernate
%config(noreplace) %{_sysconfdir}/security/console.apps/ovirt-flush-caches
%config(noreplace) %{_sysconfdir}/security/console.apps/diskmapper

%attr (755,root,root) %{_datadir}/ovirt-guest-agent/ovirt-guest-agent.py*

%{_datadir}/ovirt-guest-agent/scripts/hooks/defaults/55-flush-caches
%attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/defaults/55-flush-caches.consolehelper
%attr (755,root,root) %{_datadir}/ovirt-guest-agent/scripts/hooks/defaults/flush-caches

%attr (644,root,root) %{_datadir}/ovirt-guest-agent/default.conf
%attr (644,root,root) %{_datadir}/ovirt-guest-agent/default-logger.conf

%attr (755,root,root) %{_datadir}/ovirt-guest-agent/diskmapper.script
%{_datadir}/ovirt-guest-agent/CredServer.py*
%{_datadir}/ovirt-guest-agent/GuestAgentLinux2.py*
%{_datadir}/ovirt-guest-agent/OVirtAgentLogic.py*
%{_datadir}/ovirt-guest-agent/VirtIoChannel.py*
%{_datadir}/ovirt-guest-agent/timezone.py*
%{_datadir}/ovirt-guest-agent/hooks.py*

# consolehelper symlinks
%attr (755,root,root) %{_datadir}/ovirt-guest-agent/ovirt-osinfo
%{_datadir}/ovirt-guest-agent/diskmapper
%{_datadir}/ovirt-guest-agent/ovirt-logout
%{_datadir}/ovirt-guest-agent/ovirt-flush-caches
%{_datadir}/ovirt-guest-agent/ovirt-locksession
%{_datadir}/ovirt-guest-agent/ovirt-shutdown
%{_datadir}/ovirt-guest-agent/ovirt-hibernate
%{_datadir}/ovirt-guest-agent/ovirt-container-list

%attr (755,root,root) %{_datadir}/ovirt-guest-agent/LockActiveSession.py*
%attr (755,root,root) %{_datadir}/ovirt-guest-agent/LogoutActiveUser.py*
%attr (755,root,root) %{_datadir}/ovirt-guest-agent/hibernate
%attr (755,root,root) %{_datadir}/ovirt-guest-agent/container-list

# Symlinks for the default hooks
%config(noreplace) %{_datadir}/ovirt-guest-agent/scripts/hooks/before_hibernation/55_flush-caches
%config(noreplace) %{_datadir}/ovirt-guest-agent/scripts/hooks/before_migration/55_flush-caches
%config(noreplace) %{_sysconfdir}/ovirt-guest-agent/hooks.d/before_hibernation/55_flush-caches
%config(noreplace) %{_sysconfdir}/ovirt-guest-agent/hooks.d/before_migration/55_flush-caches

%{_unitdir}/ovirt-guest-agent.service


%files pam-module
%{_moduledir}/pam_ovirt_cred.so
%exclude %{_moduledir}/pam_ovirt_cred.a
%exclude %{_moduledir}/pam_ovirt_cred.la

%files gdm-plugin
%config(noreplace) %{_sysconfdir}/pam.d/gdm-ovirtcred

%files kdm-plugin
%config(noreplace) %{_sysconfdir}/pam.d/kdm-ovirtcred
%attr (755,root,root) %{_libdir}/kde4/kgreet_ovirtcred.so

%changelog
* Tue Mar 14 2017 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.13-2
- Added extension for new channel name (Future channel name)

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.13-1.1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Tue Feb 07 2017 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.13-1
- Bump to upstream version 1.0.13

* Tue Jul 26 2016 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.12-4
- Bump to upstream version 1.0.12.2
- Fix for dependency issue - Missing dependency pygobject2

* Tue Jun 21 2016 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.12-3
- Bump to upstream version 1.0.12.1

* Mon May 23 2016 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.12-2
- Fixed the timezone issue which was introduced during packaging

* Thu May 19 2016 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.12-1
- Bump to upstream version 1.0.12

* Tue Apr 05 2016 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.11-3
- Bump to upstream version 1.0.11.3

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.11-2.3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Thu Oct 22 2015 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.11-2
- Bump to upstream version 1.0.11.1
- BZ#1271167 - Execute diskmapper elevated or it won't be working

* Mon Jul 20 2015 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.11-1
- Bump to upstream version 1.0.11

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.10.2-2.2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Mon Jun 01 2015 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.10.2-2
- Utilize _udevrulesdir macro for rules installation

* Sat May 02 2015 Kalev Lember <kalevlember@gmail.com> - 1.0.10.2-1.1
- Rebuilt for GCC 5 C++11 ABI change

* Wed Oct 01 2014 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.10.2-1
- Update to latest upstream release

* Fri Sep 26 2014 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.10-2
- Removed unnecessary runtime dependency on python-pep8

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org>
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Tue Jul 01 2014 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.10-1
- Bump to upstream version 1.0.10

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.9-3.1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Mon Mar 31 2014 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.9-3
- The ovirt-guest-agent-gdm-plugin is now noarch

* Mon Mar 31 2014 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.9-2
- Support for logind based session locking

* Mon Jan 20 2014 Vinzenz Feenstra <evilissimo@redhat.com> - 1.0.9-1
- Report swap usage of guests
- Updated pam conversation approach
- Python 2.4 compatability fix

* Fri Aug 09 2013 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.8-2
- Updated to oVirt 3.3 ovirt-guest-agent 1.0.8 released sources

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.8-1.alpha.1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu Jul 11 2013 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.8-1
- Upgraded sources to upstream 1.0.8
- Pep8 rules applied on python files
- Call restorecon on pidfile
- Report multiple IPv4 addresses per device if available
- Send 'uninstalled' notification non blocking
- fixed "modified" files after clone.
- rewrote nic's addresses functions in python 2.4 syntax.
- GNOME 3.8 no longer supports gdm plugins. Therefore it's now disabled for
  higher versions
- Added full qualified domain name reporting
- Condrestart now ensures that the pid file does not only exist, but also is
  not empty
- Added new optional parameter for shutdown to allow reboot

* Tue Feb 19 2013 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.6-6
- Using datadir as home directory
  Resolves: BZ#883124

* Thu Feb 14 2013 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.6-5
- ovirt-guest-agent-common obsoletes now ovirt-guest-agent

* Thu Feb 07 2013 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.6-4
- Removal of unused global variable _kdmrc

* Tue Jan 22 2013 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.6-3
- All config files are now 'noreplace'
- Refreshing the gtk icon cache during installation
- The package is not modifying the kdmrc any longer
- Using new systemd macros where appropriate

* Wed Dec 05 2012 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.6-2
- Upstream source adjusted for ovirt-guest-agent version 1.0.6

* Wed Dec 05 2012 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.6-1
- New upstream version 1.0.6
- Upstream build system is now taking care of folder creation
- Upstream build system is now taking care of systemd units installation

* Wed Nov 28 2012 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.5-3
- License has been changed to Apache Software License 2.0

* Fri Oct 19 2012 Vinzenz Feenstra <vfeenstr@redhat.com> - 1.0.5-2
- introduced ovirt-guest-agent-common noarch package which provides
  ovirt-guest-agent and avoids duplication of the same package content
- fixed various rpmlint errors and warnings
- added required build requires
- removed unnecessary build requires
- removed unnecessary call to autoreconf in setup section
- marked config files as such
- excluded unwanted files instead of deleting them
- removed consolehelper based symlinks - now in upstream make install

* Sun May 20 2012 Gal Hammer <ghammer@redhat.com> - 1.0.5-1
- fixed 'udevadm trigger' command line (bz#819945).
- fixed various rpmlint errors and warnings.

* Tue May 15 2012 Gal Hammer <ghammer@redhat.com> - 1.0.4-1
- replaced "with" usage with a python 2.4 compatible way.
- added files to support RHEL-5 distribution.
- added more detailed memory statistics.
- fixed build on fc-17 (use the _unitdir macro).

* Sun Apr 15 2012 Gal Hammer <ghammer@redhat.com> - 1.0.3-2
- removed the RHEL distribution support for the review process.
- removed BuildRoot header and clean section.
- fixed user creation.

* Tue Apr 10 2012 Gal Hammer <ghammer@redhat.com> - 1.0.3-1
- package was renamed to rhevm-guest-agent in RHEL distribution.
- fixed gdm-plugin build requires.
Resolves: BZ#803503

* Wed Mar 28 2012 Gal Hammer <ghammer@redhat.com> - 1.0.2-1
- included a gpl-v2 copying file.
- build the gdm-plugin using the gdm-devel package.
- added a support for RHEL distribution.

* Wed Feb 22 2012 Gal Hammer <ghammer@redhat.com> - 1.0.1-2
- updated required selinux-policy version (related to rhbz#791113).
- added a support to hibernate (s4) command.
- renamed user name to ovirtguest.
- reset version numbering after changing the package name.

* Tue Sep 27 2011 Gal Hammer <ghammer@redhat.com> - 2.3.15-1
- fixed disk usage report when mount point include spaces.
- added a minimum version for python-ethtool.
Resolves: BZ#736426

* Thu Sep 22 2011 Gal Hammer <ghammer@redhat.com> - 2.3.14-1
- added a new 'echo' command to support testing.
Resolves: BZ#736426

* Thu Sep 15 2011 Gal Hammer <ghammer@redhat.com> - 2.3.13-1
- report new network interaces information (ipv4, ipv6 and
  mac address).
- added disks usage report.
- a new json-based protocol with the vdsm.
Resolves: BZ#729252 BZ#736426

* Mon Aug  8 2011 Gal Hammer <ghammer@redhat.com> - 2.3.12-1
- replaced password masking with a fixed-length string.
Resolves: BZ#727506

* Thu Aug  4 2011 Gal Hammer <ghammer@redhat.com> - 2.3.11-1
- send an 'uninstalled' notification to vdsm
- mask the user's password in the credentials block
Resolves: BZ#727647 BZ#727506

* Mon Aug  1 2011 Gal Hammer <ghammer@redhat.com> - 2.3.10-2
- fixed selinux-policy required version.
Resolves: BZ#694088

* Mon Jul 25 2011 Gal Hammer <ghammer@redhat.com> - 2.3.10-1
- various fixes after failing the errata's rpmdiff.
- added selinux-policy dependency.
Resolves: BZ#720144 BZ#694088

* Thu Jun 16 2011 Gal Hammer <ghammer@redhat.com> - 2.3.9-1
- read report rate values from configuration file.
- replaced executing privilege commands from sudo to
  consolehelper.
Resolves: BZ#713079 BZ#632959

* Tue Jun 14 2011 Gal Hammer <ghammer@redhat.com> - 2.3.8-1
- execute the agent with a non-root user.
- changed the shutdown timeout value to work in minutes.
- update pam config files to work with selinux.
- fixed the local user check when stripping the domain part.
Resolves: BZ#632959 BZ#711428 BZ#694088 BZ#661713 BZ#681123

* Wed May 25 2011 Gal Hammer <ghammer@redhat.com> - 2.3.7-1
- stopped removing the domain part from the user name.
- show only network interfaces that are up and running.
Resolves: BZ#661713 BZ#681123 BZ#704845

* Mon Apr 4 2011 Gal Hammer <ghammer@redhat.com> - 2.3.6-1
- added kdm greeter plug-in.
Resolves: BZ#681123

* Mon Mar 14 2011 Gal Hammer <ghammer@redhat.com> - 2.3.5-1
- replaced rhevcredserver execution from blocking main loop to
  context's iteration (non-blocking).
Resolves: BZ#683493

* Thu Mar 10 2011 Gal Hammer <ghammer@redhat.com> - 2.3.4-1
- added some sleep-ing to init script in order to give udev
  some time to create the symbolic links.
- changed the kernel version condition.
Resolves: BZ#676625 BZ#681527

* Wed Mar 2 2011 Gal Hammer <ghammer@redhat.com> - 2.3.3-1
- removed unused file (rhevcredserver) from rhel-5 build.
- added udev and kernel minimum version requirment.
- fixed pid file location in spec file.
Resolves: BZ#681524 BZ#681527 BZ#681533

* Tue Mar 1 2011 Gal Hammer <ghammer@redhat.com> - 2.3.2-1
- updated the agent's makefile to work with auto-tools.
- added sub packages to support the single-sign-on feature.
- added -h parameter to shutdown command in order to halt the vm
  after shutdown.
- converted configuration file to have unix-style line ending.
- added redhat-rpm-config to build requirements in order to
  include *.pyc and *.pyo in the rpm file.
Resolves: BZ#680107 BZ#661713 BZ#679470 BZ#679451

* Wed Jan 19 2011 Gal Hammer <ghammer@redhat.com> - 2.3-7
- fixed files' mode to include execution flag.
Resolves: BZ#670476

* Mon Jan 17 2011 Gal Hammer <ghammer@redhat.com> - 2.3-6
- fixed the way the exit code was returned. the script always
  return 0 (success) because the main program ended and errors
  from the child process were lost.
Resolves: BZ#658092

* Thu Dec 23 2010 Gal Hammer <ghammer@redhat.com> - 2.3-5
- added description to startup/shutdown script in order to support
  chkconfig.
- a temporary fix to the 100% cpu usage when the vdsm doesn't
  listen to the virtio-serial.
Resolves: BZ#639702

* Sun Dec 19 2010 Gal Hammer <ghammer@redhat.com> - 2.3-4
- BZ#641886: lock command now handle both gnome and kde.
Resolves: BZ#641886

* Tue Dec 07 2010 Barak Azulay <bazulay@redhat.com> - 2.3-3
- BZ#660343 load virtio_console module before starting the daemon.
- BZ#660231 register daemon for startup.
Resolves: BZ#660343 BZ#660231

* Sun Dec 05 2010 Barak Azulay <bazulay@redhat.com> - 2.3-2
- initial build for RHEL-6
- works over vioserial
- Agent reports only heartbeats, IPs, app list
- performs: shutdown & lock (the lock works only on gnome - when
  ConsoleKit & gnome-screensaver is installed)
Resolves: BZ#613059

* Fri Aug 27 2010 Gal Hammer <ghammer@redhat.com> - 2.3-1
- Initial build.
