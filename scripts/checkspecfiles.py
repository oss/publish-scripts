#!/usr/bin/env python

import glob, os, shutil, string

SENDMAIL = "/usr/lib/sendmail" # sendmail location

repos = ["testing", "unstable"]
for repo in repos:
	os.chdir("/rpm/CHECK_PEND.%s" %repo)
	os.system('mkdir tmp/')
	files = glob.glob("*.src.rpm")
	flog = open('/var/adm/publish.log', 'a')
	
	for file in files:
		os.system("cp %s tmp/" %file)

	os.chdir("tmp/")
	for file in files:
		os.popen("bash /usr/local/bin/publish/extractrpm.sh %s" %file)

	source_folder = r"/rpm/CHECK_PEND.%s/tmp" %repo
	pend_error = r"/rpm/pending.error"

	extension = ".spec"
	findstr = "%changelog"
	findstr1 = "%doc"
	findstr2 = "%files"
	findstr3 = "%defattr"
	rejfiles = 0
	rejrpms = ""
	rejrpm = ""
	rejected = 0
	rejectedspecs = []
	acceptedspecs = []
	no_changelog = []
	no_doc = []
	no_files = []
	no_defattr = []

	for filename in os.listdir(source_folder):
		source_file = os.path.join(source_folder, filename)
		if source_file.endswith(extension):
			changelog = 1
			doc = 1
			files = 1
			defattr = 1
			rejected = 0
			if not findstr in open(source_file).read():
				changelog = 0
				no_changelog.append(1)
				rejected = 1
			if not findstr1 in open(source_file).read():
				doc = 0
				no_doc.append(1)
				rejected = 1
			if not findstr2 in open(source_file).read():
				files = 0
				no_files.append(1)
				rejected = 1
			if not findstr3 in open(source_file).read():
				defattr = 0
				no_defattr.append(1)
				rejected = 1
			if rejected:
				rejfiles = 1
				rejectedspecs.append(filename)
				if changelog:
					no_changelog.append(0)
				if doc:
					no_doc.append(0)
				if files:
					no_files.append(0)
				if defattr:
					no_defattr.append(0)
				print >> flog, "%s failed spec file checking" % (source_file)
			else:
				print >> flog, "%s passed spec file checking" % (source_file)
				acceptedspecs.append(filename)

	if repo == "testing":
		os.chdir("/rpm/CHECK_PEND.%s" %repo)
		for i in rejectedspecs:
			rejrpm=i
			rejrpm=rejrpm[:-5]
			rejrpm=rejrpm+"*"
			rejrpms = glob.glob(rejrpm)
			
			for p in rejrpms:
				os.system("mv %s /rpm/pending.error/" %p)

	if rejfiles:
		p=os.popen("%s -t" % SENDMAIL, "w")
		p.write("To: oss-rpm@oss.rutgers.edu\n")
		if repo == "testing":
			p.write("Subject: Rejected: %s\n" % (rejectedspecs))
		else:
			p.write("Subject: Warning: %s failed spec file check\n" % (rejectedspecs))
		p.write("\n") # blank line separating headers from body
		p.write("SPEC FILE CHECKING\n")
		p.write("Repository: %s\n\n" %repo)
		p.write("Passed spec files\n")
		p.write(string.join(acceptedspecs, "\n"))
		if repo == "testing":
			p.write("\n\nRejected spec files\n")
		else:
			p.write("\n\nFailed spec files\n")
		p.write(string.join(rejectedspecs, "\n"))
		p.write("\n\nReason(s) for failure\n")
		index = 0
		for i in rejectedspecs:
			p.write("%s:\n" %i)
			if no_files[index]: 
				p.write("missing files section\n")
			if no_defattr[index]:
				p.write("missing file attributes\n")
			if no_doc[index]:
				p.write("missing doc entry\n")
			if no_changelog[index]: 
				p.write("missing changelog\n")
			p.write("\n")
			index = index + 1
		sts = p.close()
		if sts != 0:
			print >> flog, "Sendmail exit status", sts

	os.chdir("/rpm/CHECK_PEND.%s" %repo)
	os.system("rm -rf tmp/")
