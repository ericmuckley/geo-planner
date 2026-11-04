"""Seal terminal typed entry metadata without repeating its preparation."""
import close_osm_car_paid_host_v1 as closer

closer.STAGES['entry-records']=('us-osm-car-entry-records-v1','entry-records')

if __name__=='__main__':closer.close('entry-records')
