"""Close terminal saved-shading diagnosis without producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-shading'
    closer.STAGES[key]=('us-osm-water-shading-diagnostic-v1',key)
    closer.close(key)
