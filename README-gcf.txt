[[PageOutline]]
{{{
#!comment
This is formatted as a wiki page, currently for trac:
README-gcf.txt -> https://github.com/GENI-NSF/geni-tools/wiki/GCF-Quick-Start
}}}

= gcf Configuration and Test Run =
This is a quick configuration guide for the GCF software package. Run
these 4 steps to get the sample API implementations running so as to
test the installation. Full usage instructions for each step are in
README.txt

 1. Create gcf_config
{{{
cd gcf
cp gcf_config.sample gcf_config
}}}

Optional: Edit `gcf_config` if you want to change settings from the default.
 ''Note: for a test run edits are not needed. Do this only if you want to change settings from the defaults.''

 2. Create certificates and run the GENI Clearinghouse. 
  In terminal one:
{{{
cd gcf
python src/gen-certs.py
python src/gcf-ch.py
}}}

 3. Run the GENI Aggregate Manager in a second terminal:
{{{
python src/gcf-am.py
}}}

 4. Run the gcf client test script in a third terminal window:
{{{
python src/gcf-test.py 
}}}

You should see output like this:
{{{
$ python src/gcf-test.py 
INFO:gcf-test:CH Server is https://localhost:8000/. Using keyfile /home/jkarlin/dev/gcf/alice-key.pem, certfile /home/jkarlin/dev/gcf/alice-cert.pem
INFO:gcf-test:AM Server is https://localhost:8001/. Using keyfile /home/jkarlin/dev/gcf/alice-key.pem, certfile /home/jkarlin/dev/gcf/alice-cert.pem
Slice Creation SUCCESS: URN = urn:publicid:IDN+geni:gpo:gcf+slice+1468-659:127.0.0.1%3A8000
Testing GetVersion... passed
Testing ListResources... passed
Testing CreateSliver... passed
Testing SliverStatus... passed
Testing ListResources... passed
Testing RenewSliver... passed. (Result: False)
Testing DeleteSliver... passed
Testing ListResources... passed
Second Slice URN = urn:publicid:IDN+geni:gpo:gcf+slice+065e-c63:127.0.0.1%3A8000
Testing ListResources... passed
Testing CreateSliver... passed
Testing Shutdown... passed
}}}

= Next Steps =

If you ran in to issues or your output looks different
 - Confirm you followed the install instructions including dependencies
 - See [wiki:OmniTroubleShoot the Omni Troubleshooting page] for more detailed help

Look at the source for the reference aggregate manager to understand
how the API and credentials are used, or to implement your own AM.

See README-omni.txt to try the Omni client for talking to multiple
aggregate managers and control frameworks.

Try federating your test GCF aggregate manager with another clearinghouse. 
For details, see README.txt

Further reading is on the GENI Wiki, as listed in README.txt.
