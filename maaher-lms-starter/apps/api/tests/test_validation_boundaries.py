"""Raw JSON must yield safe422, never surrogate/date-overflow HTTP500."""
import json
import pytest
from test_assignments import assignment,content,get,staff
from test_learning import learning
from test_enrollment import enrollment_case
from test_courses import author,detail,write


@pytest.mark.parametrize('date',['0001-01-01T00:00:00+01:00','9999-12-31T23:59:59-01:00','0001-01-01T00:00:00+23:59','9999-12-31T23:59:59-23:59'])
def test_extreme_offset_deadline_is422_and_does_not_append_version(assignment,date):
    c=assignment;identity,headers,_=c['author'];before=staff(c).json()
    response=identity[0].post('/assignments/'+c['aid'],headers=headers,json={'version':before['version'],**content(due_at=date)})
    assert response.status_code==422,response.text
    assert staff(c).json()['version']==before['version']
    assert staff(c).json()['draft']['id']==before['draft']['id']
    assert all('input' not in error and 'ctx' not in error for error in response.json()['detail'])


@pytest.mark.parametrize('target',['task_title','task_instructions','task_starter','task_rubric','draft_source','draft_note','lesson_content','lesson_title','unknown_key'])
def test_raw_surrogates_are_safe422_and_do_not_leak_input(assignment,target):
    c=assignment;identity,headers,cid=c['author'];client=identity[0]
    secret='not-for-validation-response'
    data={'version':staff(c).json()['version'],**content()};path='/assignments/'+c['aid']
    if target.startswith('task_'):
        field={'task_title':'title','task_instructions':'instructions','task_starter':'starter_code'}
        if target=='task_rubric':data['rubric']=[{'criterion':secret+'\ud800','max_points':100}]
        else:data[field[target]]=secret+'\ud800'
    elif target.startswith('draft_'):
        client=c['student'];path='/work/assignments/'+c['aid']+'/draft'
        data={'version_id':get(c).json()['published']['id'],'revision':0,'source_code':'Source','note':''}
        data['source_code' if target=='draft_source' else 'note']=secret+'\udfff'
    elif target.startswith('lesson_'):
        path=f'/courses/{cid}/modules/{c["mid"]}/lessons/{c["lid"]}'
        data={'version':detail(c['author'])['version'],'title':'Lesson','content':'Valid'}
        data['content' if target=='lesson_content' else 'title']=secret+'\ud800'
    else:data['\ud800']='extra'
    # ensure_ascii emits a literal JSON escape; the transport itself stays UTF8.
    response=client.post(path,headers={**headers,'content-type':'application/json'},content=json.dumps(data,ensure_ascii=True).encode('ascii'))
    assert response.status_code==422,response.text
    response.content.decode('utf8')
    assert secret not in response.text
    assert all('input' not in error and 'ctx' not in error for error in response.json()['detail'])



def test_valid_json_surrogate_pair_is_normal_unicode_and_can_save(assignment):
    c=assignment;source='print("Halo 😀")'
    data={'version_id':get(c).json()['published']['id'],'revision':0,'source_code':source,'note':'Catatan 🇮🇩'}
    response=c['student'].post('/work/assignments/'+c['aid']+'/draft',headers={**c['author'][1],'content-type':'application/json'},content=json.dumps(data,ensure_ascii=True).encode('ascii'))
    assert response.status_code==200,response.text
    assert get(c).json()['draft']['source_code']==source
