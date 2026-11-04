"""Close the terminal read-only mask diagnostic, without recomputation."""
import close_osm_car_paid_host_v1 as closer

closer.STAGES['mask-diagnostic']=('us-osm-car-mask-diagnostic-v1','mask-diagnostic')

if __name__=='__main__':closer.close('mask-diagnostic')
