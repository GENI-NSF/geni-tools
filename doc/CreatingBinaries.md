# Creating geni-tools Windows and Mac Binaries
When creating a geni-tools release, we create binaries for installing the Omni and Stitcher tools on Windows and MAC. These binaries must be tested as part of the release process. See the [release process documentation](IssuingReleases.md) for details.

Note that these instructions have not been repeated from scratch recently; there may be issues with new version numbers. If you update the version of any package used in the release, update [the License file](../windows_install/LICENSE.TXT). And try to keep the versions the same across Windows and Mac.

## Windows
Support files are located in `geni-tools/windows_install`. You will need a Windows machine/VM, preferably not one on which you are doing development.

### Install Dependencies
* Python 2.7.6: http://python.org/ftp/python/2.7.6/python-2.7.6.msi
* pip:
 * See http://docs.python-guide.org/en/latest/starting/install/win/
 * `python get-pip.py`
* easy_install:
 * `python ez_setup.py`
* M2Crypto 0.20.2: http://chandlerproject.org/pub/Projects/MeTooCrypto/M2Crypto-0.20.2.win32-py2.7.exe
 * Building from scratch is possible, but unreliable.
* pyOpenSSL: `pip install pyOpenSSL==0.14`
* swigwin
 * http://sourceforge.net/projects/swig/files/swigwin/swigwin-2.0.12/swigwin-2.0.12.zip/download?use_mirror=hivelocity
 * Extract into `C:\Program Files\swig`
* OpenSSL:
 * http://www.microsoft.com/downloads/details.aspx?familyid=9B2DA534-3E03-4391-8A4D-074B9F2BC1BF
 * http://slproweb.com/download/Win32OpenSSL-1_0_1g.exe
  * Should probably be replaced with https://slproweb.com/download/Win32OpenSSL-1_0_2d.exe, but must update the [LICENSE file](../windows_install/LICENSE.TXT) appropriately
* dateutil
 * http://labix.org/download/python-dateutil/python-dateutil-1.5.tar.gz
 * After extracting the file into `C:\Python27\Lib\site-packages`, copy the `dateutil` folder and paste it into the `\Lib\site-packages\` folder in your Python folder (usually `C:\Python27\`)
* Inno Setup 5: http://www.jrsoftware.org/isdl.php (last successfully used version 5.5.4)
* py2exe: http://sourceforge.net/projects/py2exe/files/py2exe/0.6.9/py2exe-0.6.9.win32-py2.7.exe/download

### System setup
* Create a 'tmp': `mkdir C:\tmp`
* Create a `~/.gcf`
* Edit the environment
 * Choose `Control Panel` and search for `PATH` in the search box.
 * Click on `Edit environment variables for your account`
 * If the `PATH` variable does not exist, create it by clicking `New...` and set the `Variable name` to `PATH` and the `Variable value` to `C:\Python27;C:\Users\local_user\gcf\src;C:\Users\local_user\gcf\examples`
 * If the `PATH` variable already exists, append ";" and the above to the PATH variable. Be sure to include the ";".
 * Similarly set `PYTHONPATH` to `C:\Users\local_user\gcf\src;C:\Users\local_user\gcf\examples`

### Get geni-tools
* Download the latest tarball from Github, and untar in `C:\Users\local_user\gcf` (or edit `package_builder.iss` and other instructions appropriately)

### Test
* From your install source directory, (i.e. `C:\Users\local_users\gcf\src`) do:
 * `omni.py -h`
* Download your omni bundle from the GENI Portal to the `Downloads` folder
* `omni-configure.py`
* `omni.py getusercred`
* `omni.py -a gpo-ig getversion`
* More tests are better

### Build exes
* `cd C:/Users/local_user/gcf/src`
* `python ..\windows_install\setup.py py2exe`
This should create two folders under `src`: `dist` and `build`.

### Test
* `cd dist`
* `omni.exe -h`
* `stitcher.exe -h`
* `omni-configure.exe -h`
* `readyToLogin.exe -h`
* `clear-passphrases.exe -h`
* `addMemberToSliceAndSlivers.exe -h`
* More tests are better

### Create installer

The installer setup file is `package_builder.iss`. It was created using http://sourceforge.net/projects/istool/ (which must be run as administrator)

* Run `Inno Setup` (e.g. client the shortcut on the desktop).
* Open `package_builder.iss` file. All files included are named here (hence the paths above must be as specified)
* Press the Green Arrow (Run Button).
* Test installation.
 * Inno Setup will likely run the setup tool itself automatically.
  * Check the menu items all open the proper files: Disclaimer opens License, 2 web links, and the uninstall tool
 * Follow the rest of the install instructions starting with step 2 [here](https://github.com/GENI-NSF/geni-tools/wiki/Windows#install)
  * Put the Omni tools on your path
 * Open a new command window, and test that all the executables run

Installer will be something like `C:\Users\local_user\gcf\executables\omniTools-2.10-win-setup.exe`

## Mac
Support files are located in `geni-tools/mac_install`. You will need a MAC, preferably not one on which you are doing development.

### Install Dependencies
* Python 2.7.6
 * Do not install via brew. It will not work.
 * Reset path so this version of python is used:
  * Edit `~/.profile`: `export PATH=/usr/local/bin:$PATH`
  * `source ~/.profile`
  * Confirm with `which python`
* XCode
 * Test if it is intalled using `xcode-select -p`
 * Use App Center to get Xcode
* Homebrew
 * `ruby -e "$(curl -fsSL https://raw.github.com/Homebrew/homebrew/go/install)"`
 * Follow any instructions after install, such as `brew doctor`
* Pip
 * `sudo easy_install pip`
* Install GCF specific dependencies. 
Here we specify version numbers known to work, and matching those listed in `windows_install/LICENSE.txt`.
 * `sudo chmod 777 /Library/Python/2.7/site-packages`
 * `brew install swig`
 * `pip install M2Crypto==0.22.3`
  * Ignore warnings
 * `brew install libxmlsec1`
 * `pip install python-dateutil==1.5`
 * `sudo pip install pyopenssl==0.14`
 * Test install using `python -i` and then `import M2Crypto` or `import dateutil`

Note that the most recent version numbers used for key packages were:
```
libxml2-python (2.9.1)
M2Crypto (0.22.3)
pip (1.5.4)
py2app (0.8)
pyOpenSSL (0.14)
python-dateutil (1.5)
pytz (2012d)
/Library/Caches/Homebrew/gnutls-3.2.12.1.mavericks.bottle.tar.gz
/Library/Caches/Homebrew/libgcrypt-1.6.1.mavericks.bottle.tar.gz
/Library/Caches/Homebrew/libxml2-2.9.1.mavericks.bottle.tar.gz
/Library/Caches/Homebrew/libxmlsec1-1.2.19.tar.gz
```

### Update PATH
Ensure PATH and PYTHONPAH are set.
For example, in bash, edit `.bashrc`:
```
# set PATH so it includes geni software if it exists
if [ -d "<PATH-TO-GENI-TOOLS-DIR>/src" ] ; then
    PATH="<PATH-TO-GENI-TOOLS-DIR>/src:<PATH-TO-GENI-TOOLS-DIR>/examples:$PATH"
    export PYTHONPATH="<PATH-TO-GENI-TOOLS-DIR>/src:$PYTHONPATH" 
fi
```
Then do: `source ~/.bashrc`

### Get latest geni-tools
Download the tarball from github, for example, and untar it.

The remainder of these instructions assume you have created `~/geni-tools`.

### Get `mac_install` images
The releases by default do not include two images required for creating the release on a MAC. Download these files separately and put them in `~/geni-tools/mac_install`:
* https://raw.githubusercontent.com/GENI-NSF/geni-tools/master/mac_install/OmniGraphic.png
* https://raw.githubusercontent.com/GENI-NSF/geni-tools/master/mac_install/background.png

### Run basic tests
* Run `omni-configure.py -h`
* Run `omni.py -h`
* Run `omni-configure` on an actual Omni bundle from the GENI Portal
* Run `omni.py -o getusercred`
* Run `omni.py -a ig-gpo getversion`

### Create release directories
* `mkdir -p ~/omniTools/omniTools-2.10` (fixing numbers)
* Note that the top level directory must not have the name of the final volume, and is encoded in `makeMacdmg.sh`.

### Change icon for directory
Change the icon for the `omniTools-2.10` directory to `OmniGraphic.png`:
(See http://support.apple.com/kb/ht2493)

* In Finder, navigate to and open (in preview) `geni-tools/mac_install/OmniGraphic.png`
* `Edit->Select All`, then `Copy`
* In Finder, navigate to the `new ~/omniTools/omniTools-2.10` directory
* `Command-I` (Or right click then `Get Info`)
* Click the folder icon in the top left
* `Paste`

### Build applications
* `cd ~\geni-tools\src`
* `chmod u_x ../mac_install/makeMacdmg.sh`
* `../mac_install/makeMacdmg.sh`
Lots of stuff will print out.

### Build the disk image
* `Applications -> Utilities -> Disk Utility`
* `File -> New -> Disk Image from Folder`
* Select `~/omniTools`
* Save the image as `omniTools-2.10-mac-rc1-try1` (or whatever)
* Change `Image Format` to `read+write`
* If it fails with `Resource Busy`, try closing all other apps and windows, empty the trash, and try again
* Double click the .dmg name to mount the disk
* Rename the mounted volume to remove the `-rc1` bit
* Open the volume in Finder
* Open a new Finder window and navigate to the `omniTools-2.10` folder within the mounted volume, so you can see `background.png`
* Select the volume and hit `Cmd-J`
* Towards the bottom of that window, change `Background` from `White` to `Picture`
* Select `background.png` from the other Finder window and drag that to the space shown
* Close that info window
* Re-organize the new Finder window with a background, so `omniTools-2.10` is to left of the arrow and `Applications` to the right, and the 2 .txt files are one above the other. Then resize the window to fit well.
* Close the Finder and info windows
* In `Disk Utility`, select the DMG
* Click `Convert`
* `Image Format -> compressed`
* Click `OK` to replace the existing .dmg
* Click the .dmg and select `Open`
* Confirm it comes up with the background, re-organized. Confirm also that the image is read-only by trying to change the layout of the icons.
* Close `Disk Utility`

### Final steps
* Test dmg
 * Open the dmg
 * Test doing the install by dragging `OmniTools` to `Applications`
 * Follow the [install instructions](https://github.com/GENI-NSF/geni-tools/wiki/MacOS#install) and confirm that `stitcher -h` works at the very least
* Un-install
 * In finder, drag `omniTools` to the trash
* Eject the `omniTools` dmg
* Rename dmg to something like `omniTools-2.10-mac-rc1.dmg`
