"""Seal terminal V2 closure attribution; preserve V1 and never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['source-gap-closures-v2']=('us-osm-source-gap-closures-v2','source-gap-closures-v2')
    closer.close('source-gap-closures-v2')
