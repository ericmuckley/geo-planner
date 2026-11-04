"""Close the prepared, browser-reviewed local artifact; no model replay."""
import close_osm_car_paid_host_v1 as closer

closer.STAGES['access-preview']=('us-osm-car-access-preview-v1','access-preview')

if __name__=='__main__':closer.close('access-preview')
