#! /usr/bin/python
#
# obs-monitor.py - a simple tool to monitor multiple projects in one page.
#
# (c) 2015 jw@owncloud.com, distribute under GPL-2.0 or ask.
#
# 2015-06-11, v1.0, jw -- initial draft. But can already retrigger recursively
# 2015-06-12, v1.1, jw -- supports html output
# 2015-06-22, v1.2, jw -- move excluded* into the ignore class.

import argparse, subprocess, os, re
import sys, time

verbose=0
def_apiurl="https://api.opensuse.org"
weburl="https://build.opensuse.org"

ap=argparse.ArgumentParser(description='Monitor build service results')
ap.add_argument('-r', '--retrigger-failed', action='store_true', help="Retrigger a build for all failed packages")
# ap.add_argument('-s', '--subprojects', action='store_true', help="also recurse into subprojects.")
ap.add_argument('-H', '--hide-good', action='store_true', help="hide all with good status.")
ap.add_argument('--html', action='store_true', help="produce html with links rather than plain text.")
ap.add_argument('-A', '--apiurl', help='the build service api to contact', default=def_apiurl)
ap.add_argument('proj', type=str, nargs='+', help="projects to monitor")
args=ap.parse_args()

if args.apiurl:
  if   args.apiurl in ('https://api.opensuse.org', 'obs'): weburl = 'https://build.opensuse.org'
  else: weburl = args.apiurl	# not necessarily correct.

pkg_url="%s/package/show/" % weburl
log_url="%s/package/live_build_log/" % weburl
mon_url="%s/project/monitor/" % weburl

# Keep in sync with internal_tar2obs.py obs_docker_install.py
def run(args, input=None, redirect=None, redirect_stdout=True, redirect_stderr=True, return_tuple=False, return_code=False, tee=False):
  """
     make the subprocess monster usable
  """

  if redirect is not None:
    redirect_stderr = redirect
    redirect_stdout = redirect

  if redirect_stderr:
    redirect_stderr=subprocess.PIPE
  else:
    redirect_stderr=sys.stderr

  if redirect_stdout:
    redirect_stdout=subprocess.PIPE
  else:
    redirect_stdout=sys.stdout

  in_redirect=""
  in_fd=None
  if input is not None:
    in_fd = subprocess.PIPE
    in_redirect=" (<< '%s')" % input

  if verbose: print "+ %s%s" % (args, in_redirect)
  p = subprocess.Popen(args, stdin=in_fd, stdout=redirect_stdout, stderr=redirect_stderr)
 
  (out,err) = p.communicate(input=input)

  if tee:
    if tee == True: tee=sys.stdout
    if out: print >>tee, " "+ out
    if err: print >>tee, " STDERROR: " + err

  if return_code:  return p.returncode
  if return_tuple: return (out,err,p.returncode)
  if err and out:  return out + "\nSTDERROR: " + err
  if err:          return "STDERROR: " + err
  return out

def list_subprojects(apiurl, proj):
  if not proj[-1] == ':': proj = proj + ':'	# assert trailing colon
  subs = []
  for prj in run(["osc", "-A"+apiurl, "ls"], redirect_stderr=False).split():
    if not re.match(re.escape(proj), prj): continue
    subs.append(prj)
  return subs 

def list_packages(apiurl, proj):
  return run(["osc", "-A"+apiurl, "ls", proj], redirect_stderr=False).split()
  
def list_packages_r(apiurl, proj):
  pkgs = map(lambda x: proj+'/'+x, list_packages(apiurl, proj))
  for prj in list_subprojects(apiurl, proj):
    pkgs.extend(map(lambda x: prj+'/'+x, list_packages(apiurl, prj)))
  return pkgs

def pkg_status(apiurl, proj_pack, ignore_re=None):
  """ construct proj_pack as project_name+'/'+package_name
  """
  st={}
  # dont use 'r -v' here.
  for line in run(["osc", "-A"+apiurl, "r", proj_pack], redirect_stderr=False).split('\n'):
    s = line.split(None, 2) 
    if len(s) < 3: continue
    if ignore_re is not None:
      if re.match(ignore_re, s[2]): continue
    st[s[0]+'/'+s[1]] = s[2]
  return st

success_re = r'(excluded|succeeded|\(unpublished\))'
mapped = {
  'good': [ 'succeeded', '(unpublished)', 'succeeded*' ],
  'ignore': [ 'excluded', 'excluded*', 'disabled', 'disabled*', '*' ]
}

ret={}
tot={}
w=0
all_pkgs = list_packages_r(args.apiurl, args.proj[0])
for p in all_pkgs: 
  if len(p) > w: w=len(p)

if args.html:
  print """
<table width="100%%"><tr><td align="right"><small>%s</small></td></tr></table>
<H4>OBS build statistics for %s</H4>

<table border="0">""" % (time.ctime(), args.proj[0])

prefix=None

for p in all_pkgs:
  newprefix,_ = p.split('/')
  if prefix and prefix != newprefix:
    if args.html:
      print "<tr><td colspan=3><hr></td></tr>"
    else:
      print ""
  prefix = newprefix

  st = pkg_status(args.apiurl, p, ignore_re=None)
  rstat = {}
  cnt = {}
  for k,v in st.items():
    for mkey in mapped:
      if v in mapped[mkey]: v = mkey
    if not v in rstat: rstat[v] = []
    if not v in cnt:   cnt[v] = 0
    rstat[v].append(k)
    cnt[v] +=1

  if 'ignore' in cnt: del(cnt['ignore'])	# don't count what we do not want
  for t in cnt.keys():
    if not t in tot: tot[t] = 0
    tot[t] += cnt[t]

  if args.hide_good and 'good' in cnt: del(cnt['good'])
  if len(cnt): 
    if args.html:
      if len(cnt) == 1 and 'good' in cnt:
        stats = str(cnt)
      else:
        prj,pkg = p.split('/')
        stats = '<a href="%s/%s?pkgname=%s&succeeded=0">%s</a>' % (mon_url, prj,pkg,cnt)
      print '<tr><td><a href="%s/%s">%s</a></td><td>%s</td></tr>' % (pkg_url, p, p, stats)
    else:
      print "%-*s  %s" %(w,p, cnt)

  for retrigger in ['failed', 'unresolvable']:
    if retrigger in rstat:
      if not retrigger in ret: ret[retrigger] = 0
      ret[retrigger] += cnt[retrigger]

      if args.retrigger_failed:
        for target in rstat[retrigger]:
	  plat, arch = target.split('/') 
	  if args.html:
            print "<tr><td colspan=3><small>&nbsp;-- retrigger <a href='%s/%s/%s/%s'>%s %s/%s</a></small></td></tr>" % (log_url, p, plat, arch, p, plat, arch)
          else:
            print "\tretrigger", p, plat, arch
	  run(["osc", "-A"+args.apiurl, "rebuildpac", p, plat, arch], redirect=False)

if args.html:
  print "</table><p>total:", tot
else:
  print "total:", tot
if args.retrigger_failed: print "retriggered:", ret
