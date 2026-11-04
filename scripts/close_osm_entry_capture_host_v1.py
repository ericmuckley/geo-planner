"""Seal the terminal captured restriction-entry experiment without replaying it."""
import close_osm_car_paid_host_v1 as closer

closer.STAGES['restriction-entry-capture']=('us-osm-car-restriction-entry-capture-v1','restriction-entry-capture')

if __name__=='__main__':closer.close('restriction-entry-capture')
