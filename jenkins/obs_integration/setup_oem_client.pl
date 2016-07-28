#! /usr/bin/perl -w
#
# (c) 2014, jw@owncloud.com 
#
# setup_oem_client.pl expects that the subproject already exists.
# The branding-client package itself is not created here. Use genbranding -o to create it.
# setup_oem_client.pl adds a list of known dependencies, so that we can have all relevant binaries 
# in one repo per oem branding.
#
# 2014-08-15, jw, more parameters for obs and template change.
# 2014-10-09, jw, support for trailing slash at project name. 
#                 See setup_all_oem_client.pl for the semantics.
# 2015-01-19, jw, return failure, when osc copypac fails.
# 2015-01-22, jw, honor env OSC_CMD -- needed for rotor publish-oem-client-linux
# 2016-02-08, jw, add qt5-qt* packages for centosius.
# 2016-02-25, jw, https://github.com/owncloud/ownbrander/issues/540 
#                 switches added: use_aggregates, re_use_existing_packages.
# 2016-02-26, jw, rdelete with -m !!!
#
use Data::Dumper;
sub list_obs_pkg;

my @src_pkgs = qw{ neon cmake libqt4 libqt4-sql-plugins qtwebkit qt5keychain qtkeychain qt5-qtwebkit qt5-qttools qt5-qtbase };
my $src_prj = 'desktop';
my $dest_prj_prefix = 'oem:';
my $obs_api = 'https://obs.int.owncloud.com';
my $osc_cmd = $ENV{'OSC_CMD'} || 'osc';

my $use_aggregates = 1;			# 1: do aggregatepac instead of copypac
my $re_use_existing_packages = 0;	# 0: always from scratch

my $client_name = $ARGV[0];
die qq{
Usage: $0 oem_brandname [DESTPROJ: [obs_api [tmpl_prj]]]
       $0 oem_brandname [DESTPROJ/ [obs_api [tmpl_prj]]]

Default destination project: $dest_prj_prefix
Default obs api: $obs_api
Default template project: $src_prj

} unless $client_name;

if ($ARGV[1] and ($ARGV[1] ne $dest_prj_prefix))
  {
    $dest_prj_prefix = $ARGV[1];
    warn "submitting package $client_name to nonstandard project prefix '$dest_prj_prefix'\n";
  }

$obs_api = $ARGV[2] if defined $ARGV[2];
$src_prj = $ARGV[3] if defined $ARGV[3];

$client_name =~ s{^\Q$dest_prj_prefix\E}{};

my $dest_prj = $dest_prj_prefix . $client_name;
$dest_prj = $dest_prj_prefix if $dest_prj_prefix =~ s{/$}{};

my @existing_pkg = list_obs_pkg($obs_api, $dest_prj);
my %existing_pkg = map { $_ => 1 } @existing_pkg;


for my $pkg (@src_pkgs)
  {
    if ($existing_pkg{$pkg})
      {
        print STDERR "exists: $dest_prj $pkg\n";
	if ($re_use_existing_packages)
	  {
	    next;
	  }
	else
	  {
            my $cmd = "$osc_cmd -A$obs_api rdelete -m 'remove old copy' $dest_prj $pkg";
            print STDERR "+ $cmd\n";
            system($cmd);
	  }
      }
    my $cmd = "$osc_cmd -A$obs_api copypac $src_prj $pkg $dest_prj";
    if ($use_aggregates)
      {
        $cmd = "$osc_cmd -A$obs_api aggregatepac $src_prj $pkg $dest_prj";
      }
    print STDERR "+ $cmd\n";
    system($cmd) and exit(1);
  }


exit(0);

sub list_obs_pkg()
{
  my ($api, $prj) = @_;
  my $cmd = "$osc_cmd -A$api ls $prj";
  open(my $ifd, "$cmd 2>/dev/null|") or die "list_obs_pkg: cannot read from '$cmd'";
  my @pkgs = <$ifd>;
  chomp @pkgs;
  return @pkgs;
}
