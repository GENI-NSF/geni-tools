#!/usr/bin/env python

# Explicitly import framework files so py2exe is happy
import gcf.omnilib.frameworks.framework_apg
import gcf.omnilib.frameworks.framework_base
import gcf.omnilib.frameworks.framework_gcf
import gcf.omnilib.frameworks.framework_gch
import gcf.omnilib.frameworks.framework_gib
import gcf.omnilib.frameworks.framework_of
import gcf.omnilib.frameworks.framework_pg
import gcf.omnilib.frameworks.framework_pgch
import gcf.omnilib.frameworks.framework_sfa

if __name__ == '__main__':
  import gcf.oscript
  import sys
  sys.exit(gcf.oscript.main())
