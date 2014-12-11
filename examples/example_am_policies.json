{
    "identities" : {
    "CH1_SA" : "/tmp/cascade-sa-cert.pem",
    "CH1_MA" : "/tmp/cascade-ma-cert.pem",
    "CH_MB_SA" : "/usr/share/geni-ch/sa/sa-cert.pem",
    "CH_MB_MA" : "/usr/share/geni-ch/ma/ma-cert.pem",
    "AM" : "/home/mbrinn/.gcf/am-cert.pem"
    },
    "binders" : [
        "gcf.geni.auth.binders.Standard_Binder",
        "gcf.geni.auth.binders.SFA_Binder",
        "gcf.geni.auth.binders.Stitching_Binder",
	"gcf.geni.auth.resource_binder.MAX_Binder",
	"gcf.geni.auth.resource_binder.TOTAL_Binder",
	"gcf.geni.auth.resource_binder.HOURS_Binder",
	"gcf.geni.auth.resource_binder.User_Slice_Binder"
        ],
    "constants" : {
       "$BLUE_AUTHS" : "['urn:publicid:IDN+ch1.gpolab.bbn.com+authority+ca', 'urn:publicid:IDN+wall2.ilabt.iminds.be+authority+ca']",
       "$RED_AUTHS" :  "['urn:publicid:IDN+ch-mb.gpolab.bbn.com+authority+ca']"
    },
    "conditional_assertions" : [
        {
	  "precondition" : "True",
	  "exclusive" : true,
	  "clauses" : [
          { 
            "condition" : "$SFA_AUTHORIZED", 
            "assertion" : "AM.IS_AUTHORIZED<-$CALLER"
            },
        {
            "condition" : 
	    "'$CALLER_AUTHORITY' in $BLUE_AUTHS and ($HOUR < 6 or $HOUR > 22)",
            "assertion" : "AM.VIOLATES_SCHEDULE<-$CALLER"
            },
        {
            "condition" : 
	    "'$CALLER_AUTHORITY' in $RED_AUTHS and $AUTHORITY_NODE_TOTAL > 8",
            "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
            },
        {
            "condition" : 
	    "'$CALLER_AUTHORITY' in $BLUE_AUTHS and $AUTHORITY_NODE_TOTAL > 4",
            "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
            },
        {
	    "condition" : "$USER_NUM_SLICES > 2",
	    "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
	    },
        {
            "condition" : "$PROJECT_NODE_TOTAL > 7",
            "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
            },
        {
            "condition" : "$SLICE_NODE_HOURS > 240",
            "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
            },
        {
            "condition" : "$USER_NODE_MAX > 3",
            "assertion" : "AM.EXCEEDS_QUOTA<-$CALLER"
            },
        {
            "condition" : "'urn:publicid:IDN+ion.internet2.edu+interface+rtr.newy:ae0:gpo-eg' in $REQUESTED_STITCH_POINTS",
            "assertion" : "AM.VIOLATES_TOPOLOGY<-$CALLER"
            },
        {
            "condition" : "'urn:publicid:IDN+ch1.gpolab.bbn.com+user+bujcich' == '$CALLER'",
            "assertion" : "AM.IS_BLACKLISTED<-$CALLER"
            }
	 ]
        }
    ],
    "policies" : [
        "AM.MAY_SHUTDOWN<-CH_MB_SA.MAY_SHUTDOWN"
    ],
    "queries" : [
        {
            "statement" : "AM.IS_AUTHORIZED<-$CALLER", 
            "is_positive" : true, 
            "message" : "Authorization Falure"
            },
        {
            "statement" : "AM.EXCEEDS_QUOTA<-$CALLER", 
            "is_positive" : false,
            "message" : "Quota Exceeded"
            },
        {
            "statement" : "AM.VIOLATES_SCHEDULE<-$CALLER", 
            "is_positive" : false,
            "message" : "Schedule Violation"
            },
        {
            "statement" : "AM.VIOLATES_TOPOLOGY<-$CALLER",
            "is_positive" : false,
            "message" : "Topology Violation"
            },
        {
            "statement" : "AM.IS_BLACKLISTED<-$CALLER",
            "is_positive" : false,
            "message" : "Blacklisted"
            },
        {
            "statement" : "AM.MAY_SHUTDOWN<-$CALLER",
            "is_positive" : true,
            "message" : "Privilege Failure",
	    "condition" : "'$METHOD' in ['Shutdown_V2', 'Shutdown_V3']"
            }
        ]
    }
