# ValetRules

## Downloading a Source Package
ValetRules and NLP Core source code are provided in a tar archive for download via Artifactory. 

Log in to the SRI Artifactory web site [`https://artifactory.sri.com/`](https://artifactory.sri.com/) using the username and password that you have been given.
You can either download the software from the user interface, or if you want to download the software programmatically, you will need to use an SRI Artifactory Key. 
If you already have it, go to [Example Settings](#example-settings)

### Retrieving Your SRI Artifactory Key

To set the value of the `SRI_ARTIFACTORY_KEY` environment variable, you must retrieve your key to access the SRI Artifactory.

This key value is needed for the step in this guide in which you use a [`curl`](#curl-command) command to download files.

1.  Log in to the SRI Artifactory web site 
1.  Click on your username in the upper right of the browser window.
1.  If the key has not already been generated, then click on the circular arrow icon next to the text box on the left of the browser window to generate it.  The generated key value appears hidden.
1. Click on the eye icon to show the value of the key in the text box, and copy that value to the clipboard.
1.  Set the `SRI_ARTIFACTORY_KEY` environment variable to the key value, as described [below](#example-settings).
     - Replace the schema variable `<key>` on the right side of the example setting with the value that you paste from the clipboard
     - There are shell-specific ways to keep your key secret, such as preceding the command with a space, so that the key will not be exposed in your command history

### Example Settings

Configure a shell variable with your Artifactory Key:

```bash
export SRI_ARTIFACTORY_KEY=<key>
```

## ValetRules and NLP Core Source Code Download

The following instructions describe how to download and unpack the gzipped tar archive for the software from Artifactory. These instructions include downloading the NLP Core library which is a dependency of the ValetRules code.  It is also possible to navigate to the repository and download the tar archive from the Artifactory GUI.

The default Artifactory repository for the ValetRules software is [valet-pypi-local](https://artifactory.sri.com/artifactory/webapp/#/artifacts/browse/simple/General/valet-pypi-local).  External clients will receive a client-specific repository name for which they have read access. The following commands assume that the `VALET_REPOSITORY` variable has been set appropriately.  Note that `VALET_VERSION` and `NLP_VERSION` may differ from each other and that the use of *1.0.0* as a value is just an example.

1. Enter the following `curl` command in a terminal window to download each source package.  Note that the `SRI_ARTIFACTORY_KEY` environment variable must be set to your SRI Artifactory key.

   To download the source archive, use `curl` as follows:

     ```bash
     export REPO_BASE="https://artifactory.sri.com/artifactory/${VALET_REPOSITORY}"
     export VR_VERSION="1.0.0"
     export NLP_VERSION="1.0.0"
     curl -o "nlpcore-$NLP_VERSION.tar.gz" -H "X-JFrog-Art-Api:${SRI_ARTIFACTORY_KEY}" "$REPO_BASE/nlpcore/$NLP_VERSION/nlpcore-$NLP_VERSION.tar.gz" -v
     curl -o "valetrules-$VR_VERSION.tar.gz" -H "X-JFrog-Art-Api:${SRI_ARTIFACTORY_KEY}" "$REPO_BASE/valetrules/$VR_VERSION/valetrules-$VR_VERSION.tar.gz" -v
     ```  

     > Note that [`X-JFrog-Art-Api`](https://www.jfrog.com/confluence/display/RTF/Artifactory+REST+API) is a dedicated header required by Artifactory for secure access.

1.  The curl commands should return a status `200` if it was successful. Additionally you may run `tar tzvf` to check the contents of the archive.

1. If the file is not a valid tgz file, it may be a text file that indicates an error that occurred when attempting to download.  Correct the error and try again.

1.  Unpack each tgz file and remove the version from the directory name:

    ```bash
    tar -xzvf "nlpcore-$NLP_VERSION.tar.gz"
    mv "nlpcore-$NLP_VERSION"   nlpcore
    tar -xzvf "valetrules-$VR_VERSION.tar.gz"
    mv "valetrules-$VR_VERSION" valetrules
    ```


## Prerequisites
In addition to NLP Core, ValetRules requires: 

**Python**

Valet requires [Python 3](https://www.python.org/).

**The `plac` module**

Please see the `plac` [website](https://pypi.org/project/plac/) for information on installing the `plac` module.

The `pip` command to install `plac` is simply:

```python
pip3 install plac==1.3.0
```

More information on loading prerequisites and setting up a development environment can be found in the  **README.md** file found in `valetrules`.
