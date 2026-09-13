import math
from pathlib import Path
import pandas as pd
import pytest
from dashboard.metrics import batting_line, pitching_line, innings_text, percentile_rank, simulate_trade, game_results
from dashboard.data_loader import clean_data
from dashboard.metric_catalog import RAW_FIELDS
from dashboard.bio import _bucket

def frame(kind, **stats):
 row={c:0 for c in RAW_FIELDS[kind].values()}
 row.update(player_id=1,team_id=1,game_pk=1,season=2021,game_date='2021-05-01',team_level='A+',league_id=126)
 row.update({kind+'_'+k:v for k,v in stats.items()})
 return pd.DataFrame([row])

def test_weighted_rates_and_missingness():
 a=frame('batting',AB=4,H=2,TB=3,PA=5,BB=1)
 b=frame('batting',AB=1,H=0,TB=0,PA=1,BB=0);b['game_pk']=2
 line=batting_line(pd.concat([a,b]))
 assert line['AVG']==pytest.approx(.4)
 assert line['OBP']==pytest.approx(.5)
 assert line['SLG']==pytest.approx(.6)
 b['batting_H']=None
 assert math.isnan(batting_line(pd.concat([a,b]))['AVG'])

def test_pitching_innings_and_total_bases():
 p=frame('pitching',outs=17,ER=2,H=4,BB=1,AB=20,SO=5,HR=1,SF=1,**{'2B':1,'3B':0})
 s=pitching_line(p)
 assert innings_text(17)=='5.2'
 assert s['ERA']==pytest.approx(54/17)
 assert s['SLG']==pytest.approx(8/20)
 assert s['BABIP']==pytest.approx(3/15)

def test_catalog_recovery_keeps_every_field():
 p=frame('pitching').drop(columns=['pitching_outs','pitching_IP_str'])
 p['raw_stats_json']='{"inningsPitched":"5.2", "strikeOuts":7}'
 p['pitching_SO']=None;p['new_source_field']='retained'
 out=clean_data(p,'pitching')
 assert out.pitching_outs.iloc[0]==17
 assert out.pitching_SO.iloc[0]==7
 assert set(RAW_FIELDS['pitching'].values())<=set(out.columns)
 assert out.new_source_field.iloc[0]=='retained'

def test_percentiles_require_peers_and_handle_ties():
 assert math.isnan(percentile_rank(pd.Series([1,2]),1))
 assert percentile_rank(pd.Series([1]*5),1)==50
 assert percentile_rank(pd.Series([1,2,3,4,5]),1,lower=True)==90

def test_scenario_preserves_source_and_counts():
 df=pd.DataFrame({'team_id':[1,1,2,2],'player_id':[10,11,20,21],'H':[1,2,3,4]})
 out=simulate_trade(df,1,2,[10],[20])
 assert out.scenario_team_id.tolist()==[2,1,1,2]
 assert df.team_id.tolist()==[1,1,2,2]
 assert out.H.sum()==df.H.sum()

def test_game_results_are_not_multiplied_by_players():
 df=pd.DataFrame({'game_pk':[1,1],'team_id':[2,2],'game_date':['2021-05-01']*2,'team_score':[5,5],'opponent_score':[3,3]})
 games=game_results(df,df)
 assert len(games)==1
 assert games.Margin.iloc[0]==2

def test_status_does_not_guess_release_or_mlb():
 assert _bucket(False,None,None)=='Other / Unknown'
 assert _bucket(True,None,'Active')=='Other / Unknown'

def test_all_pages_render_sample():
 from streamlit.testing.v1 import AppTest
 root=Path(__file__).resolve().parents[1]
 app=AppTest.from_file(str(root/'Home.py'),default_timeout=90).run()
 assert not app.exception
 for page in ['1_Player_Dashboard','2_Team_Dashboard','3_Trade_Simulator','4_Metric_Guide']:
  app.switch_page('pages/'+page+'.py').run()
  assert not app.exception, [x.message for x in app.exception]

def test_pitching_and_scenario_interactions():
 from streamlit.testing.v1 import AppTest
 root=Path(__file__).resolve().parents[1]
 app=AppTest.from_file(str(root/'Home.py'),default_timeout=90).run()
 app.switch_page('pages/1_Player_Dashboard.py').run()
 app.segmented_control[0].set_value('Pitching').run()
 assert not app.exception
 app.switch_page('pages/3_Trade_Simulator.py').run()
 app.multiselect[0].select(app.multiselect[0].options[0]).run()
 app.button[-1].click().run()
 assert not app.exception, [x.message for x in app.exception]
 assert any('What changes' in x.value for x in app.markdown)
