"""Seal terminal readonly cached-way tag inventory; no replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['source-gap-way-tags']=('us-osm-source-gap-way-tags-v1','source-gap-way-tags')
    closer.close('source-gap-way-tags')
