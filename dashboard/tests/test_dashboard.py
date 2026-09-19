import math
from pathlib import Path
import pandas as pd
import pytest
from dashboard.metrics import batting_line, pitching_line, innings_text, percentile_rank, simulate_trade, game_results, player_table, split_table, rolling_rate, team_table, line_for, enriched_line
from dashboard.data_loader import clean_data
from dashboard.metric_catalog import RAW_FIELDS
from dashboard.bio import _level, _state, pool_ids
from dashboard.context import Context

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

TEAMS={"1":[1,"Yankees"],"2":[12,"Athletics"],"3":[14,"Athletics"]}

def test_level_comes_from_team_not_active_flag():
 assert _level(1,TEAMS)==(1,'MLB','Yankees')
 assert _level(2,TEAMS)[1]=='Double-A'
 assert _level(999,TEAMS)[1]=='Other league'   # independent / foreign club
 assert _level(None,TEAMS)[1]=='No team'       # never guessed as released or retired

def test_roster_state_buckets():
 assert _state('A','Active')=='Active'
 assert _state('D60','Injured 60-Day')=='Injured list'
 assert _state('DEV','Development List')=='Development list'
 assert _state('RST','Restricted List')=='Restricted list'

def test_pool_filter_separates_stayed_from_moved_up():
 b=pd.DataFrame({'player_id':[1,2,3,4,5],'current_level':['Double-A','MLB','Triple-A','High-A','No team']})
 assert pool_ids(b,'same','Double-A')=={1}
 assert pool_ids(b,'up','Double-A')=={2,3}      # No team is not "moved up"
 assert pool_ids(b,'pick','Double-A',['MLB','High-A'])=={2,4}

def test_all_pages_render_sample():
 from streamlit.testing.v1 import AppTest
 root=Path(__file__).resolve().parents[1]
 app=AppTest.from_file(str(root/'Home.py'),default_timeout=90).run()
 src=[s for s in app.sidebar.selectbox if s.label=='Source']
 src[0].set_value('Included sample').run()
 assert not app.exception
 for page in ['1_Player_Dashboard','2_Team_Dashboard','3_Trade_Simulator','4_Metric_Guide']:
  app.switch_page('pages/'+page+'.py').run()
  assert not app.exception, [x.message for x in app.exception]

def test_pitching_and_scenario_interactions():
 from streamlit.testing.v1 import AppTest
 root=Path(__file__).resolve().parents[1]
 app=AppTest.from_file(str(root/'Home.py'),default_timeout=90).run()
 src=[s for s in app.sidebar.selectbox if s.label=='Source']
 src[0].set_value('Included sample').run()
 app.switch_page('pages/1_Player_Dashboard.py').run()
 app.get('button_group')[0].set_value('Pitching').run()
 assert not app.exception
 app.switch_page('pages/3_Trade_Simulator.py').run()
 app.multiselect[0].select(int(app.multiselect[0].options[0].split('ID ')[-1])).run()
 [b for b in app.button if b.label=='Run roster scenario'][0].click().run()
 assert not app.exception, [x.message for x in app.exception]
 assert any('What changes' in x.value for x in app.markdown)

def test_context_period_labels():
 kw=dict(batting=None,pitching=None,level='A',league='L',league_id=1,source='s',location='l',start=None,end=None,revision='r')
 one=Context(seasons=(2022,2022),**kw); many=Context(seasons=(2021,2023),**kw)
 assert (one.period,one.multi_season)==('2022',False)
 assert (many.period,many.tag,many.multi_season)==('2021–2023','2021-2023',True)


def games(kind,n,player=1,**over):
 rows=[]
 for i in range(n):
  r=frame(kind,**{k:(v[i] if isinstance(v,list) else v) for k,v in over.items()}).iloc[0].to_dict()
  r.update(game_pk=100+i,player_id=player,game_date=f'2021-05-{i+1:02d}',player_full_name='P%d'%player,team_name='T',pos_group='OF',role='SP')
  rows.append(r)
 df=pd.DataFrame(rows)
 df['game_date']=pd.to_datetime(df['game_date'])
 return df

def test_grouped_table_matches_one_player_at_a_time():
 """The vectorised table must equal the per-player line it replaced."""
 a=games('batting',3,player=1,AB=[4,3,5],H=[2,1,0],TB=[3,1,0],PA=[5,4,5],BB=[1,1,0],SO=[0,2,1],HR=[0,0,0])
 b=games('batting',2,player=2,AB=[4,4],H=[1,2],TB=[1,4],PA=[4,5],BB=[0,1],SO=[1,1],HR=[0,1])
 df=pd.concat([a,b],ignore_index=True)
 table=player_table(df,'batting').set_index('player_id')
 for pid in (1,2):
  one=enriched_line(df[df.player_id.eq(pid)],'batting',line_for(df,'batting'))
  for key in ('AVG','OBP','SLG','OPS','ISO','PA','G','wOBA','wRC_est'):
   assert table.loc[pid,key]==pytest.approx(one[key],nan_ok=True),key

def test_grouped_table_keeps_missing_totals_unknown():
 df=games('batting',2,AB=[4,4],H=[2,None])
 assert math.isnan(player_table(df,'batting')['AVG'].iloc[0])
 assert math.isnan(split_table(df,'batting','team_name')['AVG'].iloc[0])

def test_rolling_window_uses_only_the_trailing_games():
 df=games('batting',4,AB=[4,4,4,4],H=[4,0,0,0],TB=[4,0,0,0],PA=[4,4,4,4])
 rolling=rolling_rate(df,'batting',2,'AVG')
 assert rolling['value'].tolist()==pytest.approx([1.0,.5,0,0])
 assert rolling['Games in window'].tolist()==[1,2,2,2]

def test_team_table_counts_each_game_once():
 df=pd.DataFrame({'game_pk':[1,1,2],'team_id':[9,9,9],'team_name':['T']*3,'game_date':pd.to_datetime(['2021-05-01']*2+['2021-05-02']),
                  'team_score':[5,5,1],'opponent_score':[3,3,4],'result':['W','W','L'],'opponent_name':['O']*3})
 row=team_table(df,df.iloc[:0]).iloc[0]
 assert (row.Games,row.W,row.L,row.Margin)==(2,1,1,-1)
 assert row.W_pct==pytest.approx(.5)

def sample_app():
 from streamlit.testing.v1 import AppTest
 root=Path(__file__).resolve().parents[1]
 app=AppTest.from_file(str(root/'Home.py'),default_timeout=90).run()
 app.sidebar.selectbox(key='data_source').set_value('Included sample').run()
 app.number_input(key='overview_min_batting').set_value(0).run()
 return app

def test_a_hidden_leaderboard_says_how_to_get_the_players_back():
 from streamlit.testing.v1 import AppTest
 root=Path(__file__).resolve().parents[1]
 app=AppTest.from_file(str(root/'Home.py'),default_timeout=90).run()
 app.sidebar.selectbox(key='data_source').set_value('Included sample').run()
 app.number_input(key='overview_min_batting').set_value(500).run()
 assert any('lower the minimum' in w.value for w in app.warning),[w.value for w in app.warning]

def test_the_leaderboard_offers_every_ranked_player_to_open():
 app=sample_app()
 options=app.selectbox(key='overview_jump_batting').options
 assert options and options[0].startswith('1. ')      # ranked, matching the table above it
 assert isinstance(app.selectbox(key='overview_jump_batting').value,int)

def test_arriving_from_another_page_selects_that_player():
 app=sample_app()
 wanted=app.selectbox(key='overview_jump_batting').value
 app.session_state['_goto_player']=(wanted,'batting')
 app.session_state['player_team_batting']=None
 app.session_state['player_position_batting']='All'
 app.switch_page('pages/1_Player_Dashboard.py').run()
 assert not app.exception,[e.message for e in app.exception]
 assert app.selectbox(key='player_pick_batting').value==wanted

def test_a_player_outside_the_filters_warns_instead_of_crashing():
 app=sample_app()
 app.session_state['_goto_player']=(-1,'batting')   # id that cannot be selected
 app.switch_page('pages/1_Player_Dashboard.py').run()
 assert not app.exception,[e.message for e in app.exception]
 assert any('not in the current filters' in w.value for w in app.warning)
