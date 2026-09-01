from __future__ import annotations
from datetime import date, datetime
from Core.audit import log
from Core.db import connect
from Core.ids import next_id
from Core.text import upper_text
from Core.validation import finite_integer, finite_number, money

def _now(): return datetime.now().isoformat(timespec='seconds')
def _num(value, label, maximum=1_000_000_000):
    return finite_number(value,field=label.upper(),minimum=0,maximum=maximum,default=0)

def list_viagens():
    with connect() as c:
        rows=c.execute('''SELECT v.*,o.nome obra_nome,u.nome unidade_nome,u.uf FROM viagens v JOIN obras o ON o.id=v.obra_id JOIN unidades u ON u.id=o.unidade_id ORDER BY v.data_saida DESC,v.id DESC''').fetchall()
        out=[]
        for r in rows:
            x=dict(r)
            x['pracas']=[dict(p) for p in c.execute('''SELECT p.id,p.nome,p.op_numero FROM viagem_pracas vp JOIN pracas p ON p.id=vp.praca_id WHERE vp.viagem_id=? ORDER BY p.nome,p.op_numero''',(r['id'],))]
            out.append(x)
        return out

def create_viagem(obra_id: str, data_saida: str, praca_ids=None, municipio='', local_obra='', veiculo='', motorista='', funcionarios=0, dias=0, distancia_km=0, custo_pessoal=0, custo_frete=0, custo_total=0, observacao='', origem='MANUAL'):
    try: date.fromisoformat(data_saida)
    except Exception as exc: raise ValueError('Data de saída inválida.') from exc
    praca_ids=list(dict.fromkeys(praca_ids or [])); now=_now()
    if len(praca_ids)>500: raise ValueError('Uma viagem pode vincular no máximo 500 Praças.')
    funcionarios=finite_integer(funcionarios,field='FUNCIONÁRIOS',minimum=0,maximum=10000,default=0)
    dias=_num(dias,'Dias',3650); distancia_km=_num(distancia_km,'Distância',10_000_000); custo_pessoal=money(custo_pessoal,field='CUSTO PESSOAL'); custo_frete=money(custo_frete,field='CUSTO FRETE'); custo_total=money(custo_total,field='CUSTO TOTAL')
    if custo_total <= 0: custo_total=custo_pessoal+custo_frete
    with connect() as c:
        o=c.execute('SELECT * FROM obras WHERE id=?',(obra_id,)).fetchone()
        if not o: raise ValueError('Obra inválida.')
        for pid in praca_ids:
            p=c.execute('SELECT obra_id FROM pracas WHERE id=?',(pid,)).fetchone()
            if not p or p['obra_id']!=obra_id: raise ValueError(f'Praça {pid} não pertence à obra selecionada.')
        vid=next_id(c,'viagem','VIA')
        c.execute('''INSERT INTO viagens(id,obra_id,data_saida,municipio,local_obra,veiculo,motorista,funcionarios,dias,distancia_km,custo_pessoal,custo_frete,custo_total,observacao,origem,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(vid,obra_id,data_saida,upper_text(municipio),upper_text(local_obra),upper_text(veiculo),upper_text(motorista),funcionarios,dias,distancia_km,custo_pessoal,custo_frete,custo_total,upper_text(observacao,multiline=True),upper_text(origem) or 'MANUAL',now,now))
        c.executemany('INSERT INTO viagem_pracas(viagem_id,praca_id) VALUES(?,?)',[(vid,p) for p in praca_ids])
        log('VIAGEM_CRIADA',id=vid,obra=obra_id,data=data_saida,custo_total=custo_total,pracas=praca_ids)
        return dict(c.execute('SELECT * FROM viagens WHERE id=?',(vid,)).fetchone())

def update_viagem(viagem_id: str, data_saida: str, municipio='', local_obra='', veiculo='', motorista='', funcionarios=0, dias=0, distancia_km=0, custo_pessoal=0, custo_frete=0, custo_total=0, observacao=''):
    try: date.fromisoformat(data_saida)
    except Exception as exc: raise ValueError('Data de saída inválida.') from exc
    funcionarios=finite_integer(funcionarios,field='FUNCIONÁRIOS',minimum=0,maximum=10000,default=0); dias=_num(dias,'Dias',3650); distancia_km=_num(distancia_km,'Distância',10_000_000); custo_pessoal=money(custo_pessoal,field='CUSTO PESSOAL'); custo_frete=money(custo_frete,field='CUSTO FRETE'); custo_total=money(custo_total,field='CUSTO TOTAL')
    if custo_total<=0: custo_total=custo_pessoal+custo_frete
    with connect() as c:
        if not c.execute('SELECT 1 FROM viagens WHERE id=?',(viagem_id,)).fetchone(): raise ValueError('Viagem não encontrada.')
        c.execute('''UPDATE viagens SET data_saida=?,municipio=?,local_obra=?,veiculo=?,motorista=?,funcionarios=?,dias=?,distancia_km=?,custo_pessoal=?,custo_frete=?,custo_total=?,observacao=?,updated_at=? WHERE id=?''',(data_saida,upper_text(municipio),upper_text(local_obra),upper_text(veiculo),upper_text(motorista),funcionarios,dias,distancia_km,custo_pessoal,custo_frete,custo_total,upper_text(observacao,multiline=True),_now(),viagem_id))
        log('VIAGEM_EDITADA',id=viagem_id,custo_total=custo_total)
        return dict(c.execute('SELECT * FROM viagens WHERE id=?',(viagem_id,)).fetchone())
