"""Seal the terminal saved-map comparison artifact without model execution."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['display-refinement-preview-v1']=('us-osm-display-refinement-preview-v1','display-refinement-preview-v1')
    closer.close('display-refinement-preview-v1')
