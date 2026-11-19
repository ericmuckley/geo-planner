"""Seal terminal source closure attribution; never rerun its producer."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['source-gap-closures']=('us-osm-source-gap-closures-v1','source-gap-closures')
    closer.close('source-gap-closures')
