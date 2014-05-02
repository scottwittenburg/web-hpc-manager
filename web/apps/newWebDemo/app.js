

(function ($) {
    var baseUrl = 'http://solaris/girder/api/v1/',
    pvwebBaseUrl = 'http://solaris/apps/Visualizer/?',
    appConfig = { 'topLevelFolderId': '52f84a067bee040aa2335afc', // solaris
                  // topLevelFolderId = '5356a4947bee047b8183d5b5', // tukey
                  // topLevelFolderId = '52f908af7bee040bfaeee127', // mayall
                  'doAddFileToJobString': false,
                  // 'applicationFragment': '/apps/Visualizer/',
                  'applicationFragment': '/webapps/pvwdynamic/',
                  'hostnameFragment': ''
                  // 'hostnameFragment': '.alcf.anl.gov'
                },
    remoteConnectionsFolder = '52fe97757bee040fc657a371',
    // mySessionMgrUrlKeyVal = 'sessionManagerURL=http://solaris/girder/api/v1/remoteconnection&',
    mySessionMgrUrlKeyVal = '',
    token = null,
    imgFilePattern = new RegExp('vtk_([^_]+)_neg-([^-])-up'),
    titlePattern = new RegExp('(region[\\d]+)\\.vtk'),
    filePathPattern = new RegExp('(postProcessedRegions[^\\.]+\\.vtk)'),
    overviewPngUrl = null,
    compiledMetadataTemplate = null,
    pHash = '',
    jobDescriptor = { "schedulerType": "ANLCobalt",
                      "wallTime": "5",
                      "numberOfNodes": "1",
                      "queue": "pubnet",
                      "project": "SkySurvey" },
    // jobString = "#!/bin/sh%0A%0Aexport PATH=/home/scottwit/software/python-2.7.3/bin:\\$PATH ; export LD_LIBRARY_PATH=/home/scottwit/software/python-2.7.3/lib:\\$LD_LIBRARY_PATH ; /home/scottwit/ParaView/release-4.1.0/build/bin/pvpython /home/scottwit/ParaView/release-4.1.0/build/lib/site-packages/paraview/web/pv_web_visualizer.py --port 8000 --content /home/scottwit/ParaView/release-4.1.0/build/www --data-dir /gpfs/mira-fs0/projects/SkySurvey/scottwit/pvLaunchDemo/haloregions -f",
    jobString = "#!/bin/bash%0A%0A/home/scott/projects/ParaView/build-make-gpu/bin/pvpython /home/scott/projects/ParaView/src/Web/Python/pv_web_wavelet.py -f --data-dir /home/scott/Documents/cosmodata/haloregions --port 8000 --pipeline WaveletPipeline --content /home/scott/projects/ParaView/build-make-gpu/www --host localhost",
    // jobString = "#!/bin/bash%0A%0A/home/scott/projects/ParaView/build-make-gpu/bin/pvpython /home/scott/projects/ParaView/build-make-gpu/lib/site-packages/paraview/web/pv_web_visualizer.py --content /home/scott/projects/ParaView/build-make-gpu/www -f --data-dir /home/scott/Documents/cosmodata/haloregions --port 8000",

    // Does the work of figuring out the argument to send to visualizer
    launchPvwebFile = function(filepath, hostname) {
        var match = filePathPattern.exec(filepath);
        if (match !== null) {
            getSshCredentials(hostname, function(name, pass) {
                var url = pvwebBaseUrl + mySessionMgrUrlKeyVal +
                    'sshuser=' + name + '&sshpass=' + pass +
                    '&relFileName=' + match[1];
                console.log('pvweb points launch url: ' + url);
                $('.pvweb-iframe').attr('src', url);
                $('.pvweb-iframe-pane').show();
            });
        }
    },

    // Use the appropriate RemoteConnection to launch a pvweb instance,
    // create a secure tunnel, then connect to the pvweb instance through
    // the tunnel
    securePvwebLaunch = function(filepath, host) {
        console.log("Attempting a secure remote launch on host: " + host);

        var match = filePathPattern.exec(filepath);
        var relFilePath = '';
        if (match !== null) {
            relFilePath = match[1];
        }

        var d = findRemoteConnectionDetails(host);

        function launch(connId) {
            var url = pvwebBaseUrl +
                'sessionManagerURL=http://solaris/girder/api/v1/remoteconnection/tunnellaunch&' +
                'relFileName=' + relFilePath + '&' +
                'connectionId=' + connId + '&' +
                'remoteHost=' + host;

            console.log('pvweb launch url: ' + url);

            $('.pvweb-iframe').attr('src', url);
            $('.pvweb-iframe-pane').show();
        }

        if (d['targetConnId'] === 'none' || d['targetConnId'] === '' || d['targetConnected'] === false) {
            console.log("you are not connected, attempting to connect using following params:");
            console.log('host: ' + d['targetFqhn'] + ', connId: ' + d['targetConnId'] + ', itemId: ' + d['targetItemId']);
            connectToRemote(d['targetFqhn'], d['targetConnId'], d['targetItemId'], launch);
        } else {
            launch(d['targetConnId']);
        }
    },

    // Similar to securePvwebLaunch, except in this case we have to qsub our paraviewweb
    // job and then qstat until it's ready and running.
    scheduledPvwebLaunch = function(filepath, host) {
        console.log("Attempting a secure scheduled remote launch on host: " + host);

        var match = filePathPattern.exec(filepath);
        var relFilePath = '';
        if (match !== null) {
            relFilePath = match[1];
        }

        var d = findRemoteConnectionDetails(host);

        function interpretStatusResult(connId, jobInfo, result) {
            var jobId = jobInfo['hpcJobId'];
            var jsonResult = JSON.parse(result[0][0]);
            console.log(jsonResult);
            var statusString = jsonResult[0];
            var indicatorElt = $('.job-status-indicator.' + jobId);
            var nextCheck = 5000;

            if (statusString === 'running') {
                var readyBtn = $('.job-status-ready-btn', indicatorElt);
                $('.job-status-busy-spinner', indicatorElt).hide();
                $('.job-status-remove-btn', indicatorElt).hide();
                readyBtn.show();
                $('.job-status-label-status', indicatorElt).text(statusString);
                if (readyBtn.hasClass('fresh')) {
                    readyBtn.unbind('click');
                    readyBtn.bind('click', function(event) {
                        var btn = $(this);
                        btn.unbind('click');
                        btn.removeClass('fresh');
                        btn.css('color', 'grey');
                        var hostnamePrefix = jsonResult[1]['hostnames'];
                        var hostnameSuffix = appConfig['hostnameFragment'];
                        var connectPort = 8000;
                        var connectUrl = "http://" + hostnamePrefix + hostnameSuffix +
                            ":" + connectPort + appConfig['applicationFragment'];
                        console.log('Connect to running pvweb at url: ' + connectUrl);
                        $('.pvweb-iframe').attr('src', connectUrl);
                        $('.pvweb-iframe-pane').show();
                        event.stopPropagation();
                        event.preventDefault();
                    });
                }
                nextCheck = 5000;
            } else if (statusString === 'starting' || statusString === 'queued') {
                $('.job-status-busy-spinner', indicatorElt).show();
                $('.job-status-remove-btn', indicatorElt).hide();
                $('.job-status-ready-btn', indicatorElt).hide();
                $('.job-status-label-status', indicatorElt).text(statusString);
            } else if (statusString === 'killing' || statusString == 'exiting') {
                $('.job-status-label-status', indicatorElt).text('Finished');
            } else if (statusString === 'NO_SUCH_JOB') {
                $('.job-status-busy-spinner', indicatorElt).hide();
                $('.job-status-ready-btn', indicatorElt).hide();
                $('.job-status-remove-btn', indicatorElt).show();
                $('.job-status-label-status', indicatorElt).text('Finished');
                $('.job-status-remove-btn', indicatorElt).bind('click', function(event) {
                    // Ask Girder to do some job cleanup for us.
                    var requestData = { 'connId': connId,
                                        'girderDir': '/home/scottwit/.girder',
                                        'jobUuid': jobInfo['girderJobId'],
                                        'userHomeDir': '/home/scottwit' };
                    $.ajax({
                        type: 'POST',
                        url: baseUrl + 'remoteconnection/jobcleanup',
                        dataType: 'json',
                        data: requestData,
                        success: function(result) {
                            console.log('Returned from cleanup request:');
                            console.log(result);
                            // Then remove the ui for this job
                            indicatorElt.remove();
                        },
                        error: function(result) {
                            console.log("Error making jobcleanup POST request:");
                            console.log(result);
                            alert("Unsuccessful job cleanup result, see console.");
                        }
                    });
                    event.stopPropagation();
                    event.preventDefault();
                });
                nextCheck = -1;
            }  else {
                // Noticed this could be "killing" or "exiting" as well as above options
                console.log("OH BUMMER, what do I do with " + statusString + "?");
            }

            return nextCheck;
        }

        // Make a POST request to girder to run qstat on the remote machine
        // (currently via the remotely installed HPCJobScheduler python module)
        // and return the status of the identified job.
        function checkStatus(connId, jobInfo) {
            var jobId = jobInfo['hpcJobId'];
            console.log('Checking status, connId: ' + connId + ', jobId: ' + jobId);
            var requestData = { 'connId': connId,
                                'girderDir': '/home/scottwit/.girder',
                                'jobUuid': jobInfo['girderJobId'],
                                'jobDescriptor': JSON.stringify(jobDescriptor) }
            $.ajax({
                type: 'POST',
                url: baseUrl + 'remoteconnection/jobstatus',
                dataType: 'json',
                data: requestData,
                success: function(statResult) {
                    console.log('Got job status for jobid: ' + jobId + ', status:');
                    console.log(statResult[0][0]);
                    var nextCheck = interpretStatusResult(connId, jobInfo, statResult);
                    if (nextCheck > 0) {
                        setTimeout(function() {
                            checkStatus(connId, jobInfo);
                        }, nextCheck);
                    }
                },
                error: function(result) {
                    console.log("Error making jobschedule POST request:");
                    console.log(result);
                    alert("Unsuccessful job schedule result, see console.");
                }
            });
        }

        // Once the job has been scheduled, we want to add some ui to remind
        // us of it's existence, to give us a way to interact once the job is
        // running, as well as to give us an indicator when it is finished.
        function scheduled(connId, result) {
            console.log('Successfully scheduled job:');
            console.log(result);
            var jobId = result['hpcJobId'];
            console.log("Now I have just the job id: " + jobId);

            // clone the status indicator
            var newDiv = $('#job-status-indicator-template')
                .clone()
                .removeAttr('id')
                .addClass(jobId);
            $('.header-bar').append(newDiv);
            $('.job-status-busy-spinner', newDiv).show();
            $('.job-status-label-id', newDiv).text(jobId);
            $('.job-status-label-status', newDiv).text('Pending...');
            $('.job-status-ready-btn', newDiv).addClass('fresh');

            newDiv.bind('click', function(event) {
                event.stopPropagation();
                event.preventDefault();
            });

            setTimeout(function() {
                checkStatus(connId, result);
            }, 5000);
        }

        // POST a girder request to 'remoteconnection/jobschedule' with connId in
        // the params.  This rest api route will result in qsub getting called on
        // the remote connection, and we should get a jobid back from the request
        function launch(connId) {
            // Some of this stuff can be retrieved from Girder (either here or
            // inside the Girder plugin) eventually.  For now, we'll just put
            // in enough to get the demo working.
            if (appConfig['doAddFileToJobString']) {
                var match = filePathPattern.exec(filepath);
                if (match !== null) {
                    filepath = ' --load-file ' + match[1];
                }
            } else {
                filepath = '';
            }
            console.log("Launching a pvweb job to visualize: " + filepath);
            var launchData = { 'connId': connId,
                               'girderDir': '/home/scottwit/.girder',
                               'userHomeDir': '/home/scottwit',
                               'jobDescriptor': JSON.stringify(jobDescriptor),
                               'jobString': jobString + filepath + "%0A" };
            $.ajax({
                type: 'POST',
                url: baseUrl + 'remoteconnection/jobschedule',
                dataType: 'json',
                data: launchData,
                success: function(result) {
                    scheduled(connId, result);
                },
                error: function(result) {
                    console.log("Error making jobschedule POST request:");
                    console.log(result);
                    alert("Unsuccessful job schedule result, see console.");
                }
            });
        }

        // Kick things off: If we're not already connected, connect and then
        // launch.  Otherwise, just launch.
        if (d['targetConnId'] === 'none' || d['targetConnId'] === '' || d['targetConnected'] === false) {
            console.log("you are not connected, attempting to connect using following params:");
            console.log('host: ' + d['targetFqhn'] + ', connId: ' + d['targetConnId'] + ', itemId: ' + d['targetItemId']);
            connectToRemote(d['targetFqhn'], d['targetConnId'], d['targetItemId'], launch);
        } else {
            launch(d['targetConnId']);
        }
    },

    /// This is where I can choose from the various forms of launching
    /// with which I have experimented in this prototype application
    //launchFunction = launchPvwebFile,
    //launchFunction = securePvwebLaunch,
    launchFunction = scheduledPvwebLaunch,

    // Update the number of items showing in the results column
    updateResultsCount = function(count) {
        $('.search-results-count').text(count);
    },

    // An object which stores all the girder items so that later I can
    // reload them all into my collection if the filter is cleared,
    // without having to query them from Girder again
    cosmoDatum = {},

    // Define the CosmoData model to extend Backbone.Model
    CosmoData = Backbone.Model.extend({}),

    // Remote connection model
    RemoteConnection = Backbone.Model.extend({}),

    // Define the CosmoView to extend Backbone.View
    CosmoSummaryView = Backbone.View.extend({
        tagName: 'div',

        // Cache the template function for a single item.
        todoTpl: _.template( $('.cosmo-summary-template').html() ),

        events: {
            'click .image-thumb': 'loadImage',
            'click .show-metadata-btn': 'showMetadata'
        },

        // Re-render the titles of the todo item.
        render: function() {
            // console.log('rendering a cosmodata');
            this.$el.html( this.todoTpl( this.model.toJSON() ) );
            return this;
        },

        showMetadata: function(e) {
            var that = this;
            var itemId = this.model.attributes.itemId;
            var jsonObj = cosmoDatum[itemId].attributes;
            var elt = compiledMetadataTemplate(jsonObj);
            var jqElt = $(elt);

            $('.viewport-container').append(jqElt);

            $('.close-cosmo-element-btn', jqElt).bind('click', function(evt) {
                var me = $(this);
                me.parent().parent().remove();
            });

            var lx, ly;

            $('.cosmo-element-title-bar', jqElt).bind('mousedown', function(evt) {
                $('.cosmo-element-container').css('z-index', '10');
                jqElt.css('z-index', '11');
                lx = evt.pageX;
                ly = evt.pageY;
                $(this).bind('mousemove', function(evt) {
                    var dx = evt.pageX - lx;
                    var dy = evt.pageY -ly;
                    jqElt.css('top', '+=' + dy);
                    jqElt.css('left', '+=' + dx);
                    lx = evt.pageX;
                    ly = evt.pageY;
                });
            });

            $('.cosmo-element-title-bar', jqElt).bind('mouseup', function(evt) {
                $('.cosmo-element-title-bar', jqElt).unbind('mousemove');
            });

            $('.image-thumb', jqElt).click(function(evt) { that.loadImage(evt); });
            $('.launch-pvweb-button-magvel', jqElt).click(function(evt) {
                that.launchVolViz(evt);
            });
            $('.launch-pvweb-button-volren', jqElt).click(function(evt) {
                that.launchPtsViz(evt);
            });
        },

        // Called to load the full size image in the viewer when thumb is clicked
        loadImage: function(e) {
            $('.pvweb-iframe').attr('src', '');
            $('.pvweb-iframe-pane').hide();
            $('.full-size-image').attr('src', e.target.src);
        },

        // Called to launch paraviewweb to visualize the magnitude of velocity points data
        launchPtsViz: function(e) {
            launchFunction(this.model.attributes.velocityMagnitudeVtkFile,
                           this.model.attributes.hostname);
        },

        // Called to launch paraviewweb to visualize the volume data
        launchVolViz: function(e) {
            launchFunction(this.model.attributes.volumeVtkFile,
                           this.model.attributes.hostname);
        }
    }),

    // Define the RemoteConnectionView to extend Backbone.View
    RemoteConnectionView = Backbone.View.extend({
        tagName: 'tr',

        // Cache the template function for a single item.
        tpl: _.template( $('.remote-connection-template').html() ),

        // Re-render the titles of the todo item.
        render: function() {
            // console.log('rendering a cosmodata');
            this.$el.html( this.tpl( this.model.toJSON() ) );
            return this;
        }
    }),

    // Define a simple collection for the CosmoData objects, with just a filter
    CosmoCollection = Backbone.Collection.extend({
        model: CosmoData,
    }),

    // Define a collection for the RemoteConnection objects
    RemoteConnectionCollection = Backbone.Collection.extend({
        model: RemoteConnection
    }),

    // A collection instance
    cosmoDataCollection = new CosmoCollection(),

    // Another collection instance, for remote connections
    remoteConnCollection = new RemoteConnectionCollection(),

    // Our overall **AppView** is the top-level piece of UI.
    AppView = Backbone.View.extend({
        // Instead of generating a new element, bind to the existing skeleton of
        // the App already present in the HTML.
        el: '.viewport-container',

        // At initialization we bind to the relevant events on the `Todos`
        // collection, when items are added or changed.
        initialize: function() {
            this.listenTo(cosmoDataCollection, 'add', this.addOne);
            this.listenTo(cosmoDataCollection, 'reset', this.addAll);
        },

        // Add a single todo item to the list by creating a view for it, and
        // appending its element to the `<ul>`.
        addOne: function( modelObj ) {
            var view = new CosmoSummaryView({ model: modelObj });
            $('.cosmodata').append(view.render().el);
            updateResultsCount(cosmoDataCollection.length);
        },

        // Add all items in the cosmoDataCollection collection at once.
        addAll: function() {
            this.$('.cosmodata').html('');
            cosmoDataCollection.each(this.addOne, this);
            updateResultsCount(cosmoDataCollection.length);
        }
    }),

    // A list view ui component
    RemoteConnectionListView = Backbone.View.extend({
        // Instead of generating a new element, bind to the existing skeleton of
        // the App already present in the HTML.
        el: '.viewport-container',

        // At initialization we bind to the relevant events on the
        // collection, when items are added or changed.
        initialize: function() {
            this.listenTo(remoteConnCollection, 'add', this.addOne);
            this.listenTo(remoteConnCollection, 'reset', this.reset);
        },

        // Add a single item to the list by creating a view for it, and
        // appending its element to the parent div.
        addOne: function( modelObj ) {
            var view = new RemoteConnectionView({ model: modelObj });
            $('.cosmo-remote-connection-table').append(view.render().el);
        },

        // Empty the list of html elements
        reset: function() {
            $('.cosmo-remote-connection-table').html('');
        }
    }),

    // An instance of a list view for the RemoteConnection items
    myRconView = new RemoteConnectionListView(),

    // An instance of the top-level list view of CosmoData items
    myAppView = new AppView();


    /*
     * Find the remote connection that matches the hostname and return
     * an object containing it's details.
     */
    function findRemoteConnectionDetails(host) {
        var details = {
            'targetConnId': 'none',
            'targetFqhn': '',
            'targetConnected': 'false',
            'targetItemId': ''
        };

        console.log("Iterating over remote connections");
        remoteConnCollection.each(function(rc) {
            if (rc.attributes.hostname === host) {
                console.log('Found remote connection, host: ' + host);
                details['targetConnId'] = rc.attributes.connectionId;
                details['targetFqhn'] = rc.attributes.hostname;
                details['targetConnected'] = rc.attributes.connected;
                details['targetItemId'] = rc.attributes.itemId;
            }
        });

        return details;
    }


    /*
     * Present dialog to collect ssh user name and password, then invoke
     * the callback with that information.  Callback should be defined to
     * take two args: username and password.
     */
    function getSshCredentials(hostname, callback) {
        $('.ssh-authenticate-button').unbind().bind('click', function(evt) {
            $('.ssh-authentication-widget').hide();
            var name = $('.ssh-username-input-field').val();
            var pass = $('.ssh-password-input-field').val();
            callback(name, pass);
        });
        $('.remote-ssh-host').text(hostname);
        $('.ssh-authentication-widget').show();
    }


    /*
     * Connect to a secure remote connection given the hostname to connect to,
     * the connection id generated and returned by the Girder remoteconnection
     * endpoint, and the id of the Girder item which contains the information
     * about the remote connection.
     */
    function connectToRemote(hostname, connectionId, itemId, onConnected) {
        console.log('Connect to host: ' + hostname + ', connId: ' + connectionId);

        function connected(connectResult, connId) {
            // 3) when (2) returns, update Girder: /item/{id}/metadata?connected=yes&connectionId={connId}
            $.ajax({
                type: 'PUT',
                url: baseUrl + 'item/' + itemId + '/metadata',
                dataType: 'json',
                headers: {'Content-Type': 'application/json; charset=UTF-8',
                          'Accept': 'application/json' },
                data: JSON.stringify({ "connected": "yes", "connectionId": connId }),
                processData: false,
                // contentType: 'application/json; charset=UTF-8',
                success: function() {
                    updateRemoteConnections();
                    if (onConnected) {
                        onConnected(connId);
                    }
                },
                error: function(result) {
                    console.log("Error making PUT request to update connection metadata:");
                    console.log(result);
                }
            });
        }

        function remoteConnect(connId) {
            // 1) show ssh password prompt
            getSshCredentials(hostname, function(name, pass) {
                // 2) make Girder call to /remoteconnection/connect.  Make it
                // a POST request to keep sensitive information out of the log
                // files.
                $.ajax({
                    type: 'POST',
                    url: baseUrl + 'remoteconnection/connect',
                    dataType: 'json',
                    data: { 'connId': connId,
                            'username': name,
                            'password': pass },
                    success: function(connectResult) {
                        connected(connectResult, connId);
                    },
                    error: function(result) {
                        console.log("Error making connect POST request:");
                        console.log(result);
                        alert("Unable to make remote connection, see console for information");
                    }
                });
            });
        }

        // If there is not yet a connection id for this remote, we need
        // to create one.  Once we have that (and also if we already
        // have one) we can make the connection
        if (connectionId === 'none' || connectionId === '') {
            // Attempt to create a remote connection
            makeGirderRequest('GET',
                              'remoteconnection/create',
                              {'fqhn': hostname},
                              function(response) {
                                  if ('connId' in response) {
                                      remoteConnect(response['connId']);
                                  } else {
                                      alert('Unable to create remote ' +
                                            'connection to ' + hostname);
                                  }
                              });
        } else {
            remoteConnect(connectionId);
        }
    }

    /*
     * Interact with (send commands to and receive results from) a
     * secure remote connection.
     */
    function interactWithRemote(hostname, connectionId) {
        console.log('Interact with host: ' + hostname + ', connId: ' + connectionId);
        $('.remote-connection-list').hide();
        $('.console-hostname').text(hostname);
        $('.remote-interact-panel').show();

        $('.command-entry-field').keypress(function(e) {
            var me = $(this);
            var command = me.val();
            if (e.keyCode == 13 && !e.shiftKey) {
                e.preventDefault();
                console.log('You entered: ' + me.val());
                makeGirderRequest('GET',
                                  'remoteconnection/command',
                                  { 'connId': connectionId,
                                    'cmdStr': command },
                                  function(result) {
                                      console.log('Result of running "' + command + '" on remote:');
                                      console.log(result);
                                      var outputContents = ""
                                      for (var idx in result[0]) {
                                          outputContents += result[0][idx];
                                      }
                                      $('.command-results-field').val(outputContents);
                                  });
            }
        });
    }

    /*
     * Disconnect the remote referenced by connectionId
     */
    function disconnectFromRemote(connectionId, itemId) {
        function updateConnectionRecord(result) {
            console.log('Result of disconnecting remote:');
            console.log(result);

            $.ajax({
                type: 'PUT',
                url: baseUrl + 'item/' + itemId + '/metadata',
                dataType: 'json',
                headers: {'Content-Type': 'application/json; charset=UTF-8',
                          'Accept': 'application/json' },
                data: JSON.stringify({ "connected": "no" }),
                processData: false,
                success: updateRemoteConnections,
                error: function(result) {
                    console.log("Error making PUT request to update connection metadata:");
                    console.log(result);
                }
            });
        }

        makeGirderRequest('GET',
                          'remoteconnection/disconnect',
                          { 'connId': connectionId },
                          updateConnectionRecord);
    }

    /*
     * Retrieve the remote connection items, use them to repopulate the
     * collection, which will result in their re-rendering.
     */
    function updateRemoteConnections() {

        function gotRemoteConnections(data) {
            remoteConnCollection.reset();
            for (var idx in data) {
                var rconItem = data[idx];
                var rcon = new RemoteConnection({
                    hostname: rconItem['meta']['fqhn'],
                    connected: (rconItem['meta']['connected'] === 'yes' ? true : false),
                    connectionId: rconItem['meta']['connectionId'],
                    itemId: rconItem['_id']
                });
                remoteConnCollection.add(rcon);
            }

            $('.conn-interact-btn').bind('click', function() {
                var me = $(this);
                interactWithRemote(me.attr('data-fqhn'), me.attr('data-connection-id'));
            });

            $('.conn-connect-btn').bind('click', function() {
                var me = $(this);
                if (me.hasClass('connect')) {
                    // console.log('Connecting');
                    connectToRemote(me.attr('data-fqhn'),
                                    me.attr('data-connection-id'),
                                    me.attr('data-item-id'));
                } else {
                    // console.log('Disconnecting');
                    disconnectFromRemote(me.attr('data-connection-id'),
                                         me.attr('data-item-id'));
                }
            });
        }

        // Attempt to get this user's remote connections
        makeGirderRequest('GET',
                          'item/',
                          {'folderId': remoteConnectionsFolder},
                          gotRemoteConnections);
    }

    /*
     * This function can be called once we have successfully authenticated
     * and got our token to use in all subsequent requests.  Here we query
     * Girder in two steps and initialize the ui with the results.
     */
    function initialize() {
        // Compile the metadata page template just this once
        compiledMetadataTemplate = _.template($('.cosmodata-template').html());

        // This function iterates over the files associated with an item
        // and constructs a url to retrieve each file.  We assume all of
        // the files that match the regular expression are png images.
        function handleItemFiles(fileArray) {
            var itemId = null;
            for (var idx in fileArray) {
                var iFile = fileArray[idx];
                itemId = iFile['itemId'];
                var filename = iFile['name'];
                var fileId = iFile['_id'];
                var match = imgFilePattern.exec(filename);
                if (match.length === 3) {
                    var keystr = match[1] + '_p' + match[2];
                    var url = baseUrl + "file/" + fileId + "/download?token=" + token;
                    if ('imageUrls' in cosmoDatum[itemId]['attributes']) {
                        cosmoDatum[itemId]['attributes']['imageUrls'][keystr] = url;
                    }
                }
            }
            if (itemId !== null) {
                cosmoDataCollection.add(cosmoDatum[itemId]);
            }
        }

        // This function iterates over the returned items, and for each one,
        // sends another Girder request to retrieve the files for the item.
        function handleItems(itemArray) {
            for (var idx in itemArray) {
                // Get files associated with item: /item/{itemId}/files
                var item = itemArray[idx];
                // var dataObj = convertItemToCosmoData(item['meta']);
                var dataObj = convertItemToCosmoData(item);
                if (dataObj !== null) {
                    cosmoDatum[item['_id']] = dataObj;
                    makeGirderRequest('GET', 'item/' + item['_id'] + '/files', {}, handleItemFiles);
                }
            }
        }

        // Trigger an asynchronous grab of all the items in the top level folder
        makeGirderRequest('GET',
                          'item/',
                          {'folderId': appConfig['topLevelFolderId']},
                          handleItems);

        // When an image is loaded into the viewer, it should possibly be centered
        $('.full-size-image').load(moveImageIntoPosition);

        // To start things off, load the overview.png image into the viewer
        overviewPngUrl = baseUrl + "file/52f8fe9d7bee040bfaeee126/download?token=" + token;
        $('.full-size-image').attr('src', overviewPngUrl);

        // As a convenience, if we click the header bar, reload the overview image
        $('.header-bar').click(function() {
            $('.pvweb-iframe').attr('src', '');
            $('.pvweb-iframe-pane').hide();
            $('.full-size-image').attr('src', overviewPngUrl);
        });

        // The search bar was hidden until login was complete, now show it
        $('.cosmo-search-bar').show();

        // This button shows or hides the remote connections listed in the
        // single remote connection folder id for this application.  It also
        // causes the list of remotes to be re-rendered based on the state of
        // the database.
        $('.show-remotes-list-btn').bind('click', function(evt) {
            evt.stopPropagation();
            var me = $(this);
            var selected = me.toggleClass("selected").hasClass("selected");
            me.toggleClass("header-btn-selected");
            $('.remote-connection-container').animate({
                left: (selected ? "+=750" : "-=750")
            }, 500, function() { /* Animation complete */ });
            if (selected) {
                updateRemoteConnections();
                $('.vtk-icon-right-open').removeClass("vtk-icon-right-open").addClass("vtk-icon-left-open");
            } else {
                $('.vtk-icon-left-open').removeClass("vtk-icon-left-open").addClass("vtk-icon-right-open");
            }
        });

        $('.header-btn').show();

        // Make sure we have all the remote connections set up in memory when
        // we get started.
        updateRemoteConnections();

        // Click handler for a button on the remote interaction panel
        $('.close-interact-btn').bind('click', function() {
            $('.remote-interact-panel').hide();
            $('.remote-connection-list').show();
            $('.command-entry-field').unbind('keypress');
        });

        // Either show the runs pane on the left or hide it
        $('.show-runs-btn').click(function(evt) {
            evt.stopPropagation();
            var me = $(this);
            var selected = me.toggleClass("selected").hasClass("selected");
            me.toggleClass("header-btn-selected");
            if (selected) {
                $('.cosmology-data-pane').css('left', '0');
                $('.visualization-pane').css('left', '600px');
            } else {
                $('.cosmology-data-pane').css('left', '-600px');
                $('.visualization-pane').css('left', '0');
            }
            moveImageIntoPosition();
        });
    }

    /*
     * Clear out the search fields and load all the items into the collection
     * again.
     */
    function clearSearchFilter() {
        $('.attr-name-field').val('');
        $('.attr-value-field').val('');
        cosmoDataCollection.reset();
        for (itemId in cosmoDatum) {
            cosmoDataCollection.add(cosmoDatum[itemId]);
        }
    }

    /*
     * Create and return a new CosmoData given an item returned from Girder
     */
    function convertItemToCosmoData(dataItem) {
        var item = dataItem['meta']
        title = null;
        if (item !== null && item !== undefined) {
            var origFile = item['originalFile'];
            if (origFile !== undefined) {
                var titleMatch =  titlePattern.exec(origFile);
                title = titleMatch[1];
            }
        }
        if (title !== null) {
            return new CosmoData({
                title: titleMatch[1],
                itemId: dataItem['_id'],
                description: dataItem['description'],
                createdDate: dataItem['created'],
                max_fof_halo_tag: item['max_fof_halo_tag'],
                max_id: item['max_id'],
                max_vel_mag: item['max_vel_mag'],
                max_vx: item['max_vx'],
                max_vy: item['max_vy'],
                max_vz: item['max_vz'],
                max_x: item['max_x'],
                max_y: item['max_y'],
                max_z: item['max_z'],
                min_fof_halo_tag: item['min_fof_halo_tag'],
                min_id: item['min_id'],
                min_vel_mag: item['min_vel_mag'],
                min_vx: item['min_vx'],
                min_vy: item['min_vy'],
                min_vz: item['min_vz'],
                min_x: item['min_x'],
                min_y: item['min_y'],
                min_z: item['min_z'],
                hostname: item['hostname'],
                originalFile: item['originalFile'],
                outputImageDir: item['outputImageDir'],
                velocityMagnitudeVtkFile: item['velocityMagnitudeVtkFile'],
                volumeVtkFile: item['volumeVtkFile'],
                imageUrls: { 'vol_px': '',
                             'pts_px': '',
                             'vol_py': '',
                             'pts_py': '',
                             'vol_pz': '',
                             'pts_pz': '' }
            });
        } else {
            return null;
        }
    }

    /*
     * Convenience function to make a girder request.  This function
     * builds the query string out of the params object, then makes
     * an ajax request to the method and url given.  When the ajax
     * call returns successfully, the successCallback is called with
     * the result.
     */
    function makeGirderRequest(method, path, params, successCallback) {
        // Build the query string from the key value pairs in params
        queryString = ""
        sep = "?"
        for (key in params) {
            queryString += sep + key + "=" + params[key]
            sep = "&"
        }

        // Now make the asynchronous request
        $.ajax({
            type: method,
            url: baseUrl + path + queryString,
            dataType: 'json',
            success: successCallback,
            error: function(result) {
                console.log("Rest request error: method = " + method +
                            ", path = " + path + ", query = " + queryString);
                console.log(result);
            }
        });
    }

    /*
     * This function moves the image into the center of it's container in
     * the dimensions in which the container is larger than the image.
     * Where the image is larger than it's container, it is positioned at
     * the top or left.
     */
    function moveImageIntoPosition() {
        var container = $('.cosmology-image-pane');
        var containerWidth = container.width();
        var containerHeight = container.height();
        var imageElt = $('.full-size-image');
        var imageWidth = imageElt.width();
        var imageHeight = imageElt.height();

        if (containerWidth > imageWidth) {
            imageElt.css('left', ((containerWidth - imageWidth) / 2.0));
        }

        if (containerHeight > imageHeight) {
            imageElt.css('top', ((containerHeight - imageHeight) / 2.0));
        }
    }

    /*
     * When the page has loaded, we first need to authenticate.  If
     * that process completes successfully, we can initialize the
     * application.
     */
    $( document ).ready( function() {
        $('.login-screen').hide();
        $('.cosmo-search-bar').hide();
        $('.ssh-authentication-widget').hide();
        $('.header-btn').hide();
        $('.attr-name-field').val('');
        $('.attr-value-field').val('');
        // $('.title-element').text("Cosmo Test Now Ready");

        $('.authenticate-button').bind('click', function() {
            var name = $('.name-input-field').val();
            var password = $('.password-input-field').val();
            console.log("You entered: " + name + ", " + password);

            pHash = btoa(name + ":" + password);

            $.ajax ({
                type: 'GET',
                url: baseUrl + 'user/authentication',
                dataType: 'json',
                async: false,
                beforeSend: function(xhr) {
                    xhr.setRequestHeader("Authorization", "Basic " + btoa(name + ":" + password));
                },
                success: function (result) {
                    console.log('Authentication succeeded');
                    console.log(result);
                    $('.login-screen').hide();
                    token = result['authToken']['token'];
                    initialize();
                },
                error: function( result ) {
                    console.log("Authentication failed");
                    console.log(result);
                    alert("Authentication failure");
                    $('.login-screen').hide();
                }
            });
        });

        $( window ).resize(moveImageIntoPosition);

        if (token === null) {
            console.log('Showing login screen');
            $('.login-screen').show();
        }
    });
}(jQuery));
