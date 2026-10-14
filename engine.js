/* LIFE Financial Studio — portable, local-only calculation engine.
 * Port of 2026-10-08 GAS v25 assumptions; NOT a validated tax/benefit forecast.
 * This file deliberately contains no family-specific personal data or API keys.
 */
(function(root){
'use strict';
const STUDENT_NAMES=['長男','次男','三男','四男'];
const num=v=>{const n=Number(String(v??'').replace(/,/g,''));return Number.isFinite(n)?n:0;};
const date=s=>{
  if(!s)return null;
  const m=String(s).match(/^(\d{4})-(\d{2})-(\d{2})$/);if(!m)return null;
  const d=new Date(+m[1],+m[2]-1,+m[3],12);
  return d.getFullYear()===+m[1]&&d.getMonth()===+m[2]-1&&d.getDate()===+m[3]?d:null;
};
const pmt=(r,n,p)=>!p?0:n<=0?0:!r?p/n:p*r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);
function students(info){return [1,2,3,4].filter(i=>i<4||info.kid4_has==='yes').map(i=>({key:'kid'+i,name:STUDENT_NAMES[i-1],birth:date(info['kid'+i+'_birth']),order:i}));}
function category(a){return a<0?'なし':a<3?'0-2歳':a<6?'3-5歳':a<12?'小学校':a<15?'中学校':a<18?'高校':a<22?'大学':'なし';}
function grade(i){return i<-2?'幼保':i<=0?'幼保':i<=6?'小'+i:i<=9?'中'+(i-6):i<=12?'高'+(i-9):i<=16?'大'+(i-12):'卒';}
// 4月2日〜翌年4月1日生まれを一つの学年にする。schoolYearは暦年ではなく4月開始年度。
function cohortYear(birth){return birth.getFullYear()-((birth.getMonth()===3&&birth.getDate()===1)||birth.getMonth()<3?1:0);}
function gradeAt(birth,year,month){return (month<4?year-1:year)-cohortYear(birth)-6;}
function stageForGrade(g){return g<=-3?'0-2歳':g<=0?'3-5歳':g<=6?'小学校':g<=9?'中学校':g<=12?'高校':g<=16?'大学':'なし';}
const monthIndex=(y,m)=>y*12+m;
// 誕生月の翌月から、18歳到達後の最初の3月31日までを月単位で集計。
function fiscalEndForAge(birth,age){const yr=birth.getFullYear()+age;return ((birth.getMonth()<3||(birth.getMonth()===3&&birth.getDate()===1))?yr:yr+1)*12+3;}
function allowanceForMonth(kids,child,year,month){
  const born=monthIndex(child.birth.getFullYear(),child.birth.getMonth()+1);
  const now=monthIndex(year,month);
  if(now<=born||now>fiscalEndForAge(child.birth,18))return 0;
  // 扶養・経済的負担が継続していることを仮定。実際は確認が必要。
  const eligible=kids.filter(k=>k.birth&&monthIndex(k.birth.getFullYear(),k.birth.getMonth()+1)<=now&&now<=fiscalEndForAge(k.birth,22));
  const elder=eligible.filter(k=>k.birth.getTime()<child.birth.getTime()||(k.birth.getTime()===child.birth.getTime()&&k.order<child.order)).length;
  if(elder>=2)return 30000;
  const third=monthIndex(child.birth.getFullYear()+3,child.birth.getMonth()+1);
  return now<=third?15000:10000;
}
function yearlyAllowance(info,kids,year){
  if(info.child_allowance_mode!=='yes')return 0;
  let total=0;for(let month=1;month<=12;month++)for(const child of kids)if(child.birth)total+=allowanceForMonth(kids,child,year,month);
  return total;
}
function yearlyPension(info,person,birth,year){
  const annual=num(info[person+'_pension_amount']);if(!annual)return 0;
  const startingAge=info[person+'_pension_age']===''||info[person+'_pension_age']===undefined?65:num(info[person+'_pension_age']);
  // 老齢年金は誕生日前日の65歳到達月の翌月から権利が発生する概算（繰上げ・繰下げは額を入力）。
  let eligibilityYear=birth.getFullYear()+startingAge,eligibilityMonth=birth.getMonth()+1;
  if(birth.getDate()===1){eligibilityMonth--;if(eligibilityMonth===0){eligibilityMonth=12;eligibilityYear--;}}
  let amount=0;for(let month=1;month<=12;month++)if(monthIndex(year,month)>monthIndex(eligibilityYear,eligibilityMonth))amount+=annual/12;
  return amount;
}
function validate(info){
  for(const k of ['husband_birth','wife_birth'])if(!date(info[k]))throw Error(k+'：日付が未入力または不正です');
  if(info.kid4_has==='yes'&&!date(info.kid4_birth))throw Error('4人目の生年月日が未入力です');
  for(const k of ['kid1_birth','kid2_birth','kid3_birth'])if(info[k]&&!date(info[k]))throw Error(k+'：日付が不正です');
  for(const p of ['husband','wife']){
    const pensionAge=info[p+'_pension_age'];
    if(pensionAge!==undefined&&pensionAge!==''&&(!Number.isInteger(Number(pensionAge))||num(pensionAge)<60||num(pensionAge)>75))throw Error(p+'の年金受給開始年齢は60〜75歳で指定してください');
    if(num(info[p+'_pension_amount'])<0)throw Error(p+'の年金年額は0円以上にしてください');
    const g=num(info[p+'_income_growth']);
    if(g<=-100||g>100||Math.abs(g*10-Math.round(g*10))>1e-7)throw Error(p+'の収入増減率を確認してください');
  }
  for(const [k,v] of Object.entries(info)){
    if(k.includes('_birth')||typeof v!=='string'||v==='')continue;
    if(/(?:_month_net|_bonus_net|_cost|_amount|_balance|_return|_growth|_freq|_years|_price|_age|_investment|_savings)$/.test(k)&&!Number.isFinite(Number(v.replace(/,/g,''))))throw Error(k+'は数字で入力してください');
  }
  if(num(info.investment_return)<-100||num(info.living_cost_growth)<-100)throw Error('増減率は-100%以上にしてください');
  if(num(info.loan_principal)>0&&!date(info.loan_start_date))throw Error('住宅ローン開始日を入力してください');
  if(num(info.loan_principal)>0&&(info.loan_rate_initial===undefined||String(info.loan_rate_initial)===''||!Number.isFinite(Number(info.loan_rate_initial))||num(info.loan_rate_initial)<0))throw Error('住宅ローンの初期金利を0%以上で入力してください');
  if(num(info.loan_prepay_annual_amount)>0&&(!num(info.loan_prepay_annual_start)||!num(info.loan_prepay_annual_end)))throw Error('定期繰上返済の開始年・終了年を入力してください');
  if(num(info.loan_prepay_once_amount)>0&&!date(info.loan_prepay_once_date))throw Error('一回繰上返済の実行日を入力してください');
  if(num(info.loan_principal)>0&&(num(info.loan_years)<1||num(info.loan_years)>60))throw Error('住宅ローン期間は1〜60年で指定してください');
  if(num(info.loan_principal)>0&&num(info.loan_main_principal)>num(info.loan_principal))throw Error('毎月返済分の元本が借入総額を超えています');
  if(info.loan_prepay_once_date&&!date(info.loan_prepay_once_date))throw Error('一回繰上返済日が不正です');
  if(info.has_future_rate==='yes'){
    const seen=new Set();
    for(let i=1;i<=10;i++){
      const [y,m,r]=['y','m','v'].map(k=>String(info['fr_'+k+'_'+i]??''));
      if([y,m,r].some(Boolean)&&![y,m,r].every(Boolean))throw Error('金利変更 '+i+' 行は年月と金利を揃えてください');
      if(!y)continue;
      if(!Number.isInteger(+y)||+y<2000||!Number.isInteger(+m)||+m<1||+m>12||!Number.isFinite(+r)||+r<0)throw Error('金利変更 '+i+' 行が不正です');
      const k=y+'-'+m;if(seen.has(k))throw Error('金利変更年月が重複しています');seen.add(k);
    }
  }
}
function education(info,startYear,duration){
  // 学年・費用区分は毎月4月に更新。暦年の金額は1〜12月の在籍費用を集計する。
  const result=[],kids=students(info),cost={jhs:{public:500000,private:1200000},hs:{public:600000,private:1000000},univ:{nat_lit:1200000,nat_sci:1400000,pri_lit:1600000,pri_sci:1800000}};
  const lessons={'3-5歳':{low:0,normal:120000,high:360000},'小学校':{low:60000,normal:240000,high:480000},'中学校':{low:120000,normal:360000,high:840000},'高校':{low:120000,normal:480000,high:1000000}};
  for(let j=0;j<duration;j++){
    const year=startYear+j;
    for(const child of kids){
      if(!child.birth)continue;
      const byStage=new Map();
      for(let month=1;month<=12;month++){
        // 出生前には通園料などを発生させない。
        if(monthIndex(year,month)<monthIndex(child.birth.getFullYear(),child.birth.getMonth()+1))continue;
        const g=gradeAt(child.birth,year,month),cat=stageForGrade(g);
        if(cat==='なし')continue;
        const row=byStage.get(cat)||{year,child:child.name,order:child.order,age:year-child.birth.getFullYear(),stage:cat,key:child.key,tuition:0,lessons:0,subsidy:0,net:0,months:0};
        const k=child.key,univType=info[k+'_univ_type']||'nat_lit';let monthTuition=0,monthSubsidy=0;
        if(cat==='0-2歳')monthTuition=child.order===1?num(info.hoikuen_max_month):child.order===2?num(info.hoikuen_max_month)/2:0;
        if(cat==='3-5歳')monthTuition=info.age3to5_type==='yochien'?240000/12:0;
        if(cat==='小学校')monthTuition=300000/12;
        if(cat==='中学校')monthTuition=(cost.jhs[info[k+'_jhs_type']]??cost.jhs.public)/12;
        if(cat==='高校'){
          monthTuition=(cost.hs[info[k+'_hs_type']]??cost.hs.public)/12;
          if(info.hs_free_use==='yes')monthSubsidy=Math.min(monthTuition,457000/12); // 高校補助は旧概算のまま
        }
        if(cat==='大学'){
          const annualTuition=cost.univ[univType]??cost.univ.nat_lit;
          monthTuition=annualTuition/12+(info[k+'_univ_living']==='alone'?1200000/12:0);
          const dependentCount=kids.filter(other=>other.birth&&monthIndex(other.birth.getFullYear(),other.birth.getMonth()+1)<=monthIndex(year,month)&&monthIndex(year,month)<=fiscalEndForAge(other.birth,22)).length;
          // 公的制度は税情報・申請・学業要件等で判定される。ここでは人数のみの概算。
          if(info.univ_free_use==='yes'&&year>=2025&&dependentCount>=3){
            const cap=univType.startsWith('pri_')?700000:540000;
            monthSubsidy=Math.min(annualTuition,cap)/12; // 家賃等を減免対象とみなさない
          }
        }
        const lesson=(lessons[cat]?.[info.extra_activity_level||'normal']??0)/12;
        row.tuition+=monthTuition;row.subsidy+=monthSubsidy;row.lessons+=lesson;row.months++;
        byStage.set(cat,row);
      }
      for(const row of byStage.values()){
        row.tuition=Math.round(row.tuition);row.subsidy=Math.round(row.subsidy);row.lessons=Math.round(row.lessons);
        row.net=Math.max(0,row.tuition-row.subsidy)+row.lessons;
        result.push(row);
      }
    }
  }
  return result;
}
function annualMortgagePayment(rate,pM,pB,term){if(term<=0)return 0;const r=num(rate)/100;return Math.round(pmt(r/12,term*12,pM)*12+pmt(r/2,term*2,pB)*2);}
function mortgageSchedule(info){
  const birth=date(info.husband_birth),start=date(info.loan_start_date),principal=num(info.loan_principal),term=num(info.loan_years);
  if(!principal||!start||!term)return [];
  const rawMain=info.loan_main_principal,main=rawMain===''||rawMain===undefined?principal:num(rawMain),bonus=Math.max(0,principal-main);
  let balance=principal,rate=num(info.loan_rate_initial),monthly=annualMortgagePayment(rate,main,bonus,term)/12,y=start.getFullYear(),m=start.getMonth()+1;
  const custom=[];
  if(info.has_future_rate==='yes')for(let i=1;i<=10;i++){
    const yy=num(info['fr_y_'+i]),mm=num(info['fr_m_'+i]),raw=info['fr_v_'+i],v=Number(raw);
    if(yy>0&&mm>=1&&mm<=12&&raw!==''&&raw!==undefined&&v>=0)custom.push({year:yy,month:mm,rate:v});
  }
  const schedule=[],periods=Math.round(term*12);let d={year:y,startBalance:balance,standardPay:0,prepay:0,interest:0,endBalance:balance,rate};
  for(let i=1;i<=periods&&balance>0;i++){
    const cr=custom.find(r=>r.year===y&&r.month===m);if(cr)rate=cr.rate;
    if(i>1&&(i-1)%60===0){const ratio=main/principal,remaining=(periods+1-i)/12,next=annualMortgagePayment(rate,balance*ratio,balance*(1-ratio),remaining)/12;monthly=Math.min(next,monthly*1.25);}
    const interest=balance*rate/1200,pay=Math.min(monthly,balance+interest);
    balance-=pay-interest;d.standardPay+=pay;d.interest+=interest;d.rate=rate;
    const yearly=num(info.loan_prepay_annual_amount)>0&&y>=num(info.loan_prepay_annual_start)&&y<=num(info.loan_prepay_annual_end)&&m===(num(info.loan_prepay_annual_month)||3)?num(info.loan_prepay_annual_amount):0;
    const once=date(info.loan_prepay_once_date),single=once&&once.getFullYear()===y&&once.getMonth()+1===m?num(info.loan_prepay_once_amount):0;
    const paid=Math.min(yearly+single,Math.max(0,balance));balance-=paid;d.prepay+=paid;
    if(m===12||balance<=0||i===periods){d.endBalance=Math.max(0,balance);d.totalPay=d.standardPay+d.prepay;d.hAge=birth?y-birth.getFullYear():'-';schedule.push({...d});d={year:y+1,startBalance:balance,standardPay:0,prepay:0,interest:0,endBalance:balance,rate};}
    if(++m>12){m=1;y++;}
  }
  return schedule;
}
function settleAssets(cash,invest,surplus,planned,rate){
  invest=Math.max(0,invest*(1+rate/100));cash+=surplus;
  if(cash<0){const sell=Math.min(invest,-cash);invest-=sell;cash+=sell;}
  const contribution=Math.min(Math.max(0,planned),Math.max(0,cash));
  cash-=contribution;invest+=contribution;
  return {cash,invest,debt:Math.max(0,-cash),total:cash+invest,contribution};
}
function calculate(info,{startYear=new Date().getFullYear()}={}){
  validate(info);const hBirth=date(info.husband_birth),wBirth=date(info.wife_birth);
  const duration=Math.max(startYear+30,hBirth?hBirth.getFullYear()+90:startYear+60)-startYear+1;
  const kids=students(info),edu=education(info,startYear,duration),byYear=new Map(),mortgage=mortgageSchedule(info),mortByYear=new Map(mortgage.map(m=>[m.year,m]));
  for(const r of edu)byYear.set(r.year,(byYear.get(r.year)||0)+r.net);
  const birthYears=new Set(kids.filter(k=>k.birth).map(k=>k.birth.getFullYear()));
  const k1=kids[0]?.birth,k1Univ=k1?k1.getFullYear()+18:9999;
  let lastGrad=0;for(const kid of kids)if(kid.birth)lastGrad=Math.max(lastGrad,kid.birth.getFullYear()+22);if(!lastGrad)lastGrad=9999;
  const retirement=p=>info[p+'_retire_has']==='yes'&&date(info[p+'_birth'])?date(info[p+'_birth']).getFullYear()+num(info[p+'_retire_age']):9999;
  const hRet=retirement('husband'),wRet=retirement('wife'),cashflow=[];
  let cash=num(info.current_savings),invest=num(info.current_invest_balance);
  for(let i=0;i<duration;i++){
    const year=startYear+i,ha=year-hBirth.getFullYear(),wa=year-wBirth.getFullYear();
    const salary=(p,age,ret)=>{
      if(year>ret||(p==='wife'&&birthYears.has(year)))return 0;
      const base=num(info[p+'_month_net'])*12+num(info[p+'_bonus_net']),g=num(info[p+'_income_growth'])/100,peak=num(info[p+'_peak_age'])||60;
      if(age<=peak)return base*Math.pow(1+g,i);
      return base*Math.pow(1+g,Math.max(0,peak-(age-i)))*Math.pow(1-g,age-peak);
    };
    let income=salary('husband',ha,hRet)+salary('wife',wa,wRet);
    income+=yearlyPension(info,'husband',hBirth,year)+yearlyPension(info,'wife',wBirth,year);
    if(year===hRet)income+=num(info.husband_retire_amount);
    if(year===wRet)income+=num(info.wife_retire_amount);
    if(year===num(info.extra_income_year))income+=num(info.extra_income_amount);
    income+=yearlyAllowance(info,kids,year);
    income=Math.round(income);
    const base=num(info.living_cost_annual);let living=base;
    if(year<lastGrad){const years=year>=k1Univ?Math.max(0,k1Univ-startYear):i;living=base*Math.pow(1+num(info.living_cost_growth)/100,years);
      kids.forEach(k=>{if(k.birth){const age=year-k.birth.getFullYear();if(age>=18&&age<=21)living-=num(info[info[k.key+'_univ_living']==='alone'?'living_reduce_alone':'living_reduce_home'])*12;}});
    }
    living=Math.round(Math.max(0,living));
    let maint=info.large_maintenance_has==='yes'&&year===num(info.large_maintenance_year)?num(info.large_maintenance_cost):0;
    const app=num(info.appliance_replace_years),freq=num(info.car_replace_freq);
    if(app>0&&i!==0&&i%app===0)maint+=num(info.appliance_replace_cost);
    const car=ha<75&&info.car_has==='yes'&&freq>0&&i!==0&&i%freq===0?Math.round(num(info.car_price)):0;
    const travel=ha<75?Math.round(num(info.travel_cost)):0;
    const house=Math.round((mortByYear.get(year)?.totalPay||0)+maint),educationCost=Math.round(byYear.get(year)||0),expenses=educationCost+living+house+car+travel;
    const assets=settleAssets(cash,invest,income-expenses,year>=wRet?0:num(info.annual_investment),num(info.investment_return));cash=assets.cash;invest=assets.invest;
    const labels=[1,2,3,4].map(order=>{
      const k=kids.find(k=>k.order===order);if(!k?.birth)return '-';const a=year-k.birth.getFullYear();if(a<0)return '出生前';
      return a+'歳('+grade(gradeAt(k.birth,year,4))+')';
    });
    cashflow.push([year,ha,wa,...labels,income,educationCost,living,house,car,travel,expenses,Math.round(invest),Math.round(cash),Math.round(assets.total),Math.round(assets.debt),income-expenses,Math.round(assets.contribution)]);
  }
  const breakdown=[];
  for(const child of kids){
    if(!child.birth)continue;
    for(const stage of ['0-2歳','3-5歳','小学校','中学校','高校','大学']){
      const rows=edu.filter(r=>r.order===child.order&&r.stage===stage);
      if(!rows.length)continue;
      breakdown.push({child:child.name,stage,gross:rows.reduce((a,r)=>a+r.tuition+r.lessons,0),subsidy:rows.reduce((a,r)=>a+r.subsidy,0),net:rows.reduce((a,r)=>a+r.net,0)});
    }
  }
  return {status:'OK',cashflow,mortgageSchedule:mortgage,eduSummary:[...byYear].sort((a,b)=>a[0]-b[0]),educationBreakdown:breakdown,kid4_has:info.kid4_has==='yes',startYear,assumptionVersion:'v1.1-policy-corrections-remaining-approximations'};
}
const api={calculate,validate,education,mortgageSchedule,settleAssets,category,gradeAt,yearlyAllowance,yearlyPension,version:'1.1.0-policy-corrections'};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.LifeEngine=api;
})(typeof window!=='undefined'?window:globalThis);
