import sqlite3
import math

def get_log(name,window,c,g):
	db_name = "result/log/%s.%s.%s.%s.log.db" % (name,window,c,g)
	return db_name

class per(object):
	# base class of evaluation method.
	
	def __init__(self):
		self.per = {'TP':0,'TN':0,'FP':0,'FN':0}
		
	def _div(self,x,y):
		if sum(y) == 0 and sum(x) == 0:
			return 0.0
		else:
			return sum(x)/float(sum(y))

	#def step(self,dec_val,dist,dec_crit,is_reverse = 0):
	def step(self,dec_val,dist,cnt,dec_crit,is_reverse = 0):
		# upper and lower limit of distance of residue is define by sql statement.
		# ex) select performace(dec_val,-0.39,True) from valid where dist = 0 or ( dist > 5 and dist < 25 );

		# is_reverse is flag how evalute decsion value
		# "decsion value <= criteria" or "decsion value >= criteria"

		# for model labels
		#if cnt == 2:
		#	dec_val = -1*dec_val
		
		if is_reverse == 1:
			self.dec_comp = lambda dec_val,dec_crit: dec_val <= dec_crit
		else:
			self.dec_comp = lambda dec_val,dec_crit: dec_val > dec_crit
		
		if dist == 0:
			if self.dec_comp(dec_val,dec_crit):
				self.per["TP"]+=1
			else:
				self.per["FN"]+=1
		else:
			if self.dec_comp(dec_val,dec_crit):
				self.per["FP"]+=1
			else:
				self.per["TN"]+=1

class acc(per):
	# evaluate function of accuracy.
	def finalize(self):
		suc = [self.per["TP"],self.per["TN"]]
		err = [self.per["FP"],self.per["FN"]]
		return self._div(suc,suc + err)


class spf(per):
	# evaluate function of specificity.
	def finalize(self):
		return self._div([self.per['TN']],[self.per['TN'],self.per['FP']])


class sns(per):
	# evaluate function of sensitivity.
	def finalize(self):
		return self._div([self.per['TP']],[self.per['TP'],self.per['FN']])


class ppv(per):
	# evaluate function of positive prediction value.
	def finalize(self):
		return self._div([self.per['TP']],[self.per['TP'],self.per['FP']])


class npv(per):
	# evaluate function of negativie prediction value.
	def finalize(self):
		return self._div([self.per['TN']],[self.per['TN'],self.per['FN']])

class mcc(per):
	def mcc(self):
		TP,TN = self.per["TP"],self.per["TN"]
		FP,FN = self.per["FP"],self.per["FN"]
		x = (TP*TN - FP*FN)
		y = math.sqrt((TP + FN)*(TN + FP)*(TP + FP)*(TN + FN))
		if y != 0:
			return x/y
		elif x == 0:
			return 0
		elif x > 0:
			return 1
		else:
			return -1
	
	def finalize(self):
		return self.mcc()




class numbp(object):
	def __init__(self):
		self.cnt = 0
	
	def step(self,dist):
		if dist == 0:
			self.cnt += 1
	
	def finalize(self):
		return self.cnt

class nearbp(object):
	def __init__(self):
		self.cnt = 0
	
	def step(self,dist,low):
			if low <= dist:
				self.cnt += 1
	
	def finalize(self):
		return self.cnt

class minmax(object):
	def __init__(self,low,up,con):
		where =  " where dist = 0 or (dist >= %s and dist <= %s)" % (low,up)
		sql = "select idch,max(dec_val),min(dec_val) from valid" + where + " group by idch;"
		self.mxmn = {idch:{"max":vmax,"min":vmin} for idch,vmax,vmin in con.execute(sql)}
	def conv(self,idch,dec_val):
		vmax = self.mxmn[idch]["max"]
		vmin = self.mxmn[idch]["min"]
		return (dec_val - vmin)/(vmax - vmin)

def norm_summary(name,window,c,g):
	sql1 = " select idch,avg(cv_mnmx(idch,dec_val)) from valid where dist = 0 group by idch;"
	sql2 = " select idch,avg(cv_mnmx(idch,dec_val)) from valid where dist > 2 group by idch;"
	with sqlite3.connect( get_log(name,window,c,g)) as con:
		mnmx = minmax(1,12000,con)
		con.create_function("cv_mnmx", 2, lambda idch,dec_val:mnmx.conv(idch,dec_val))
		for idch,dec_val in con.execute(sql1):
			print idch,dec_val

def valid_summary(name,window,c,g,thr = 0,low = 5,up = 25,reverse = 0):
	sql = """ select idch,sns(dec_val,dist,cnt,%(thr)s,%(rev)s),spf(dec_val,dist,cnt,%(thr)s,%(rev)s),
	mcc(dec_val,dist,cnt,%(thr)s,%(rev)s),numbp(dist),nearbp(dist,5),cnt
	from valid where dist = 0 or ( dist >= %(low)s and dist <= %(up)s) group by idch;""" % {"thr":thr,"rev":reverse,"low":low,"up":up}
	with sqlite3.connect( get_log(name,window,c,g)) as con:
		#mnmx = minmax(5,12000,con)
		#con.create_function("cv_mnmx", 2, lambda idch,dec_val:mnmx.conv(idch,dec_val))
		#view = """ create view mnmax_valid as select idch,cv_mnmx(idch,dec_val) as dec_val,dist from valid; """
		con.create_aggregate("sns", 5,sns)
		con.create_aggregate("spf", 5,spf)
		con.create_aggregate("mcc", 5,mcc)
		con.create_aggregate("numbp", 1,numbp)
		con.create_aggregate("nearbp", 2,nearbp)
		cur = con.cursor()
		#con.execute(view)
		for idch,v_sns,v_spf,v_mcc,nbp,nnbp,cnt in cur.execute(sql):
			yield idch,v_sns,v_spf,v_mcc,nbp,nnbp,cnt

def scop_summary(name,window,c,g,thr = 0,reverse = 0):
	sql = """ select sfamily,sns(dec_val,dist,%(thr)s,%(rev)s),spf(dec_val,dist,%(thr)s,%(rev)s),mcc(dec_val,dist,%(thr)s,%(rev)s),numbp(dist)
	from valid,scop.scop_cla where scop.scop_cla.idch = valid.idch
	and ( dist = 0 or dist > 5 and dist < 25 ) group by sfamily;
	""" % {"thr":thr,"rev":reverse}
	with sqlite3.connect("dataset/scop.db.2") as con:
		sql_scop = "select distinct sfamily,desc from scop_des,scop_cla where scop_des.scop_id = scop_cla.sfamily;"
		mapper = {scop_id:desc for scop_id,desc in con.execute(sql_scop)}
	with sqlite3.connect( get_log(name,window,c,g)) as con:
		con.execute("attach database 'dataset/scop.db.2' as scop")
		con.create_aggregate("sns", 4, sns)
		con.create_aggregate("spf", 4, spf)
		con.create_aggregate("mcc", 4, mcc)
		con.create_aggregate("numbp", 1, numbp)
		cur = con.cursor()
		for sfamily,v_sns,v_spf,v_mcc,cnt in cur.execute(sql):
			print "|".join([mapper[sfamily],str(v_sns),str(v_spf),str(v_mcc),str(cnt)])

if __name__ == "__main__":
	pass
	#norm_summary("pssm.d4.0.acd.5-25",4,-2,-10)
	#valid_summary("pssm.d4.0.cluster1.5-25.3",28,0,-12,0.562)
	#scop_summary("pssm.d4.0.cluster1.5-25.5-25.2",28,0,-12,-0.073)
	#valid_summary("pssm.d4.0.acd.5-25",36,0,-12,0.3947,1)

