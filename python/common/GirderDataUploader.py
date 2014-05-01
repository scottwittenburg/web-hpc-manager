
import json, sys, os, re
from collections import deque


class GirderDataUploader(object) :
    """
    A class which can read a json description of data to send to Girder
    and use the GirderClient class to send it.
    """

    # This is the module-level reference to the girder client python class
    gclient = None

    #-------------------------------------------------------------------------
    # Constructor
    #-------------------------------------------------------------------------
    def __init__(self, girderClientPath, hostname, portnumber, username, password) :
        """
        Constructs a GirderDataUploader by nitializing the GirderClient
        instance and preparing to upload data.

        girderClientPath: Path to location of the girderClient.py script to import

        hostname: The name of the host on which girder is running

        portnumber: The port on which girder is listening

        username: The username to use in authentication with girder

        password: Password for the user
        """
        # Create a GirderClient to interact with Girder
        if girderClientPath == None or girderClientPath == "" :
            raise Exception('Error: girderClientPath is required and should point to location where girderClient.py exists.')

        sys.path.insert(0, girderClientPath)
        gc = __import__('GirderClient')

        self.gclient = gc.GirderClient(host=hostname,
                                       port=portnumber)
        self.gclient.authenticate(username, password)

    #-------------------------------------------------------------------------
    # Stuffed this function in to fake having done postprocessing and girder
    # upload from tukey.alcf.anl.gov.
    #-------------------------------------------------------------------------
    def hackedUploadForTukey(self, itemfile, folderId) :
        itemJson = {}

        with open(itemfile) as fd :
            itemJson = json.load(fd)

        # The top level keys in this object should correspond to girder
        # items.  Each item should be associated with a metadata file
        # and a folder of images.
        for itemKey in itemJson :
            imgDir = itemJson[itemKey]['images']
            metafile = itemJson[itemKey]['metadata']

            # Read the metadata file into a json object
            metadata = None
            with open(metafile) as metaReader :
                metadata = json.load(metaReader)

            # First, hack in the tukey hostname
            metadata['hostname'] = 'tukey.alcf.anl.gov'

            # Now, hack in some fixed paths for tukey
            newPrefix = '/gpfs/mira-fs0/projects/SkySurvey/scottwit/pvLaunchDemo'
            regex = re.compile('/home/scott/Documents/cosmodata(.+)')
            valueKeysToReplace = [ 'velocityMagnitudeVtkFile',
                                   'volumeVtkFile',
                                   'outputImageDir',
                                   'originalFile' ]

            print 'Replacing keys in: ' + itemKey

            for valueKey in valueKeysToReplace :
                value = metadata[valueKey]
                matcher = regex.match(value)
                if matcher :
                    relativePath = matcher.group(1)
                    metadata[valueKey] = newPrefix + relativePath
                    print '    ' + valueKey + ': ' + metadata[valueKey]


            # First create an item and upload it's metadata
            itemDescription = 'Post processed data from original file: ' + metadata['originalFile']
            itemId = self.gclient.createItem(folderId, itemKey, itemDescription)
            self.gclient.addMetaDataToItem(itemId, metadata)

            # Now upload all the images in the images directory to this item
            imgFiles = os.listdir(imgDir)
            for imgFile in imgFiles :
                self.gclient.uploadFileToItem(itemId, os.path.join(imgDir, imgFile))


    #-------------------------------------------------------------------------
    # This function reads the supplied json file, and use it as a guide to
    # upload content (items with metadata and images) to Girder
    #-------------------------------------------------------------------------
    def uploadItems(self, itemfile, folderId) :
        """
        Read the json file describing locations of images and metadata files
        to upload to items under the specified folder.

        itemfile: The path to the file desscribing images and metadata for each
        new item that should be added to the folder.  The item file should have
        the following structure:

        {
          "region01_vtk": {
            "images": "/home/scott/Documents/cosmodata/haloregions/postProcessedRegions/region01_vtk/images",
            "metadata": "/home/scott/Documents/cosmodata/haloregions/postProcessedRegions/region01_vtk/metadata/metadata.json" },
          "region02_vtk": {
            "images": "/home/scott/Documents/cosmodata/haloregions/postProcessedRegions/region02_vtk/images",
            "metadata": "/home/scott/Documents/cosmodata/haloregions/postProcessedRegions/region02_vtk/metadata/metadata.json"}
        }

        Then each key maps to an item, where all the images in the "images"
        directory ends up as a file in the item, and all the key value pairs
        in the "metadata" file end up as key/value metadata pairs on that
        item.

        folderId: The girder folder id under which all the data should be uploaded.
        """

        itemJson = {}

        with open(itemfile) as fd :
            itemJson = json.load(fd)

        # The top level keys in this object should correspond to girder
        # items.  Each item should be associated with a metadata file
        # and a folder of images.
        for itemKey in itemJson :
            imgDir = itemJson[itemKey]['images']
            metafile = itemJson[itemKey]['metadata']

            # Read the metadata file into a json object
            metadata = None
            with open(metafile) as metaReader :
                metadata = json.load(metaReader)

            # First create an item and upload it's metadata
            itemDescription = 'Post processed data from original file: ' + metadata['originalFile']
            itemId = self.gclient.createItem(folderId, itemKey, itemDescription)
            self.gclient.addMetaDataToItem(itemId, metadata)

            # Now upload all the images in the images directory to this item
            imgFiles = os.listdir(imgDir)
            for imgFile in imgFiles :
                self.gclient.uploadFileToItem(itemId, os.path.join(imgDir, imgFile))

    #-------------------------------------------------------------------------
    # Upload a record to Girder containing information about a remote
    # connection
    #-------------------------------------------------------------------------
    def uploadRemoteConnection(self,
                               folderId,
                               name='connection name',
                               description='connection description',
                               fqhn='fully qualified host name',
                               connected='no',
                               connectionId='none',
                               girderModuleList='[]',
                               pvwebConfig='{}',
                               pvwebStatus='{}',
                               cmdConfig='{}',
                               cmdStatus='{}') :
        connectionJsonObj = { 'fqhn': fqhn, 'itemType': 'remoteConnection',
                              'girderModuleList': girderModuleList,
                              'pvwebConfig': pvwebConfig, 'pvwebStatus': pvwebStatus,
                              'cmdConfig': cmdConfig, 'cmdStatus': cmdStatus,
                              'connected': 'no', 'connectionId': 'none'}
        itemId = self.gclient.createItem(folderId, name, description)
        self.gclient.addMetaDataToItem(itemId, connectionJsonObj)

    #-------------------------------------------------------------------------
    # Upload an entire directory structure to a single item, where every file
    # in the filesystem becomes a file on the item.  Then for every file, we
    # create a metadata which maps a relative path to the Girder file id.
    #-------------------------------------------------------------------------
    def uploadDirStructureToSingleItem(self, rootPath, folderId, websiteName, websiteDescription) :
        # regular expression to allow removing base path for Girder storage
        rpRegex = re.compile('^' + rootPath + '(.+)$')

        # Create the Girder item to contain the website
        itemId = self.gclient.createItem(folderId, websiteName, websiteDescription)

        # Using a queue gives a depth-first search of the filesystem below
        # the root path.
        dirQueue = deque([rootPath])

        # This object will map relative file paths to file ids
        lookupTableJson = {}

        while True :
            try :
                nextPath = dirQueue.popleft()

                try :
                    nextList = [ os.path.join(nextPath, f) for f in os.listdir(nextPath) ]
                except OSError as osErr :
                    # The current path was not a folder, but rather a file
                    matcher = rpRegex.match(nextPath)
                    if matcher :
                        relativePath = matcher.group(1)
                        print 'Uploading file ' + relativePath
                        try :
                            fileId = self.gclient.uploadFileToItem(itemId, nextPath)
                            lookupTableJson[relativePath] = fileId
                        except Exception as inst :
                            print 'Caught exception processing file, skipping.  Details:'
                            print inst
                    else :
                        print 'ERROR: unexpected failure to match path: ' + nextPath
                    continue

                for f in nextList :
                    dirQueue.append(f)

            except IndexError as indErr :
                print 'No more items in the queue, done.'
                break

        # Now write out the lookup table as a file, so we can upload it
        outfile = os.path.join(os.getcwd(), 'lookupTable.json')
        with open(outfile, 'w') as fw:
            fw.write(json.dumps(lookupTableJson))

        fileId = self.gclient.uploadFileToItem(itemId, outfile)
        self.gclient.addMetaDataToItem(itemId, { 'lookupTableFile' : fileId })

    #-------------------------------------------------------------------------
    # Upload an entire directory structure to Girder, maintaining the strucure
    # of the filesystem paths when performing uploading.  In other words,
    # filesystem directories will be uploaded as Girder "folders", and files
    # on the filesystem will become Girder "items", where each item has it's
    # file attached.
    #-------------------------------------------------------------------------
    def uploadDirStructure(self, rootPath, folderId, websiteName, websiteDescription) :
        # regular expression to allow removing base path for Girder storage
        rpRegex = re.compile('^' + rootPath + '(.*)$')

        # Using a queue gives a breadth-first search of the filesystem below
        # the root path.
        dirQueue = deque([(rootPath, folderId)])

        while True :
            try :
                (nextPath, parentfid) = dirQueue.popleft()

                relativePath = ''
                matcher = rpRegex.match(nextPath)
                if matcher :
                    relativePath = matcher.group(1)
                else :
                    print 'ERROR: unexpected failure to match path: ' + nextPath
                    continue

                lastElt = os.path.basename(relativePath)

                try :

                    nextList = [ os.path.join(nextPath, f) for f in os.listdir(nextPath) ]

                    # We did a listdir on nextPath without an exception, so it must be a folder
                    if relativePath != '' and lastElt != '':
                        print 'Creating a folder: ' + lastElt + ', parent id: ' + parentfid
                        parentFolderId = self.gclient.createFolder(parentfid, 'folder', lastElt, '')
                    else :
                        parentFolderId = folderId

                    for f in nextList :
                        dirQueue.append((f, parentFolderId))

                except OSError as osErr :

                    # The current path was not a folder, but rather a file
                    print 'Creating an item for file: ' + relativePath

                    try :
                        itemId = self.gclient.createItem(parentfid, lastElt, '')
                        fileId = self.gclient.uploadFileToItem(itemId, nextPath)
                    except Exception as inst :
                        print 'Caught exception processing file, skipping.  Details:'
                        print inst

            except IndexError as indErr :
                print 'No more items in the queue, done.'
                break




###
### Main script, just for testing purposes
###
if __name__ == "__main__":
    # First initialize the uploader
    uploader = GirderDataUploader('./',
                                  'localhost',
                                  8080,
                                  'scottwittenburg',
                                  'password')

    # Now upload a bunch of items corresponding to cosmology data
    #itemDataFile = '/home/scott/Documents/cosmodata/haloregions/postProcessedRegions/itemdata.json'
    #folderId = '52f414017bee0420d0c0a5db'
    #uploader.uploadItems(itemDataFile, folderId)

    itemDataFile = '/home/scott/Documents/cosmodata/haloregions/tukeyPostProcessedRegions/itemdata.json'
    folderId = '5356a4947bee047b8183d5b5'
    uploader.hackedUploadForTukey(itemDataFile, folderId)

    # Or upload a remote connection record
    #
    # The id of my "Secure Remote Connections" folder is: '52fe97757bee040fc657a371'
    #uploader.uploadRemoteConnection('52fe97757bee040fc657a371',
    #                                name='Office - mayall',
    #                                description='CentOS machine in the office',
    #                                fqhn='mayall')

    #uploader.uploadRemoteConnection('52fe97757bee040fc657a371',
    #                                name='localhost',
    #                                description='This very laptop!',
    #                                fqhn='solaris')
