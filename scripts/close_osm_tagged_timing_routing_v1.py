"""Seal terminal captured routing evidence without replaying the producer."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['tagged-timing-routing-capture']=('us-osm-tagged-timing-routing-capture-v1','tagged-timing-routing-capture')
    closer.close('tagged-timing-routing-capture')
