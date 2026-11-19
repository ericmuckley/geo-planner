"""Close the metadata-only saved-tag audit; never replay the source stage."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['selected-way-tags-audit-v2']=('us-osm-selected-way-tags-audit-v2','selected-way-tags-audit-v2')
    closer.close('selected-way-tags-audit-v2')
