import { useState, useMemo, useEffect } from "react";

const IS_LOGO  = "__IS_LOGO__";
const VD_LOGO  = "__VD_LOGO__";
const DATA     = __WATCHLIST_DATA__;
const SPARKDATA= __SPARK_DATA__;
const FUNDS    = DATA.funds;
const ROWS     = DATA.rows;

const V = {
  orange:"#E84C2A", blue:"#0067B1", bg:"#ffffff", card:"#f8f9fb",
  green:"#0d7a3f", red:"#c41e2a", text:"#1a1d23", muted:"#5f6775",
  dim:"#9ca3af", border:"#e2e4e9",
};
const CHG = {
  NEW:       { bg:"#dcfce7", fg:V.green },
  LIQUIDATED:{ bg:"#fee2e2", fg:V.red   },
  INCREASED: { bg:null,      fg:V.green },
  DECREASED: { bg:null,      fg:V.red   },
  UNCHANGED: { bg:null,      fg:V.text  },
};
const BODY = "'DM Sans','Helvetica Neue',sans-serif";
const CW   = 88;   // fund col width
const ROWH = 22;   // data row height — tight

function Sparkline({ series }) {
  const W = 108, H = 28, padX = 2, padY = 2, gap = 1;
  const n = series.length;
  const barW = (W - padX*2 - gap*(n-1)) / n;
  const vals = series.filter(v => v != null);
  if (vals.length === 0) return <span style={{color:V.dim,fontSize:11}}>—</span>;
  const max = Math.max(...vals);
  if (max === 0) return <span style={{color:V.dim,fontSize:11}}>—</span>;
  const maxH = H - padY*2;
  // last non-null value for trend color
  const lastVal = vals[vals.length-1];
  const firstVal = vals[0];
  const barColor = "#3a6cc4";   // IS blue — matches the screenshot
  const emptyColor = "#d0daea"; // faint placeholder for missing quarters
  return (
    <svg width={W} height={H} style={{display:"block",margin:"0 auto"}}>
      {series.map((v, i) => {
        const x = padX + i*(barW+gap);
        if (v == null) {
          // empty slot — draw a faint thin bar at minimum height
          return <rect key={i} x={x} y={H-padY-2} width={barW} height={2} fill={emptyColor} rx={1}/>;
        }
        const bh = Math.max(2, Math.round((v/max)*maxH));
        const y  = H - padY - bh;
        return <rect key={i} x={x} y={y} width={barW} height={bh} fill={barColor} rx={1}/>;
      })}
    </svg>
  );
}

// Metric toggle: "port" = % of fund portfolio, "out" = % of shares outstanding owned
const METRICS={
  port:{key:"pct",    label:"% of Portfolio",       short:"% Port",  dp:1, fmt:"0.0%"},
  out: {key:"pctOut", label:"% of Shares Out Owned",short:"% Out",   dp:2, fmt:"0.00%"},
};
const mval=(info,mode)=>info?.[METRICS[mode].key];

function exportXlsx(rows, funds, mode="port") {
  const M=METRICS[mode];
  const XLSX=window.XLSX; if(!XLSX) return;
  const wb=XLSX.utils.book_new();
  const mf=hex=>({type:"pattern",pattern:"solid",fgColor:{rgb:hex.replace(/^#/,"FF")}});
  const mn=(bold,rgb,sz=10)=>({bold,color:{rgb},sz,name:"DM Sans"});
  const bdr={bottom:{style:"thin",color:{rgb:"FFE2E4E9"}},right:{style:"thin",color:{rgb:"FFE2E4E9"}}};
  const ctr={horizontal:"center",vertical:"center"};
  const bot={horizontal:"center",vertical:"bottom",textRotation:90};
  const hdr=["Ticker","Company","Val ($M)","% Out","# Funds",...funds];
  const wd=[hdr,...rows.map(r=>[
    r.ticker,r.name,r.sfValue,r.sfPctOut,r.sfHolders||null,
    ...funds.map(f=>{const i=r.funds[f];const v=mval(i,mode);return (v>0)?v/100:(i?.chg==="LIQUIDATED"?0:null);})
  ])];
  const ws=XLSX.utils.aoa_to_sheet(wd);
  ws["!cols"]=[{wch:9},{wch:26},{wch:10},{wch:8},{wch:7},...funds.map(()=>({wch:9}))];
  ws["!rows"]=[{hpt:56},...rows.map(()=>({hpt:15}))];
  const ga=(r,c)=>XLSX.utils.encode_cell({r,c});
  const sc=(a,v,s)=>{ws[a]={v:v??'',t:(v==null||v==='')?"s":typeof v==="string"?"s":"n",s};};
  hdr.forEach((h,c)=>{
    sc(ga(0,c),h,{fill:mf(c>=5?"FFF8F9FB":"FF0067B1"),font:mn(true,c>=5?"FF1A1D23":"FFFFFFFF",10),
      alignment:c>=5?bot:ctr,border:bdr});
  });
  rows.forEach((r,ri)=>{
    const ex=ri+1,alt=ri%2===1,rbg=alt?"FFF8F9FB":"FFFFFFFF";
    const vals=[r.ticker,r.name,r.sfValue,r.sfPctOut,r.sfHolders||null,
      ...funds.map(f=>{const i=r.funds[f];const v=mval(i,mode);return (v>0)?v/100:(i?.chg==="LIQUIDATED"?0:null);})];
    const fmts=["@","@","#,##0.0","0.0%","0",...funds.map(()=>M.fmt)];
    vals.forEach((val,c)=>{
      let bg=rbg,fgc=c===0?"FF1A1D23":"FF5F6775",bold=c===0;
      if(c>=5){
        const info=r.funds[funds[c-5]];
        if(info?.chg==="NEW")             {bg="FFDCFCE7";fgc="FF0D7A3F";bold=true;}
        else if(info?.chg==="LIQUIDATED") {bg="FFFEE2E2";fgc="FFC41E2A";bold=true;}
        else if(info?.chg==="INCREASED"&&val){fgc="FF0D7A3F";bold=true;}
        else if(info?.chg==="DECREASED"&&val){fgc="FFC41E2A";bold=true;}
      }
      sc(ga(ex,c),val,{fill:mf(bg),font:mn(bold,fgc,10),
        alignment:{horizontal:c<=1?"left":"center",vertical:"center"},numFmt:fmts[c],border:bdr});
    });
  });
  ws["!ref"]=XLSX.utils.encode_range({s:{r:0,c:0},e:{r:rows.length,c:5+funds.length-1}});
  XLSX.utils.book_append_sheet(wb,ws,"13F Matrix __QUARTER__");
  XLSX.writeFile(wb,"__XLSX_FILENAME__");
}

export default function App() {
  const [search,  setSearch]  = useState("");
  const [sortCol, setSortCol] = useState("sfHolders");
  const [sortDir, setSortDir] = useState(-1);
  const [xlsxOk,  setXlsxOk] = useState(false);
  const [mode,    setMode]    = useState("port");   // "port" | "out"
  const scrollRef = useState(null);

  useEffect(()=>{
    if(window.XLSX){setXlsxOk(true);return;}
    const s=document.createElement("script");
    s.src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
    s.onload=()=>setXlsxOk(true);
    document.head.appendChild(s);
  },[]);

  const doSort=col=>{
    if(sortCol===col) setSortDir(d=>d*-1);
    else{setSortCol(col);setSortDir(-1);}
  };

  const rows=useMemo(()=>{
    const q=search.toLowerCase();
    let rs=ROWS.filter(r=>{
      if(q&&!r.ticker.toLowerCase().includes(q)&&!r.name.toLowerCase().includes(q)) return false;
      return true;
    });
    return [...rs].sort((a,b)=>{
      const av=sortCol.startsWith("f:")?(mval(a.funds[sortCol.slice(2)],mode)??-Infinity):(a[sortCol]??-Infinity);
      const bv=sortCol.startsWith("f:")?(mval(b.funds[sortCol.slice(2)],mode)??-Infinity):(b[sortCol]??-Infinity);
      return sortDir*(av<bv?-1:av>bv?1:0);
    });
  },[search,sortCol,sortDir,mode]);

  // Sync two scroll containers so the ghost scrollbar on top mirrors the real one
  const topRef  = useState(null);
  const mainRef = useState(null);
  const syncTop  = e => { if(mainRef[0]) mainRef[0].scrollLeft=e.target.scrollLeft; };
  const syncMain = e => { if(topRef[0])  topRef[0].scrollLeft=e.target.scrollLeft;  };

  const totalW = 96+240+96+76+68+116+CW*FUNDS.length;

  const Th=({col,children,sticky=false,left=0,style={}})=>{
    const active=sortCol===col;
    return (
      <th onClick={()=>doSort(col)} style={{
        padding:"8px 10px", fontFamily:BODY, fontSize:14, fontWeight:700,
        color:active?V.text:V.muted, background:V.card,
        borderBottom:`2px solid ${V.border}`, borderRight:`1px solid ${V.border}`,
        cursor:"pointer", userSelect:"none", whiteSpace:"nowrap",
        textAlign:"center", verticalAlign:"bottom",
        position:"sticky", top:26, zIndex:sticky?6:3,
        ...(sticky?{left}:{}), ...style
      }}>
        {children}
        {active&&<span style={{color:V.orange,marginLeft:4,fontSize:12}}>{sortDir===-1?"↓":"↑"}</span>}
      </th>
    );
  };

  const FundTh=({f})=>{
    const active=sortCol===`f:${f}`;
    return (
      <th onClick={()=>doSort(`f:${f}`)} style={{
        padding:"8px 6px", width:CW, background:V.card,
        borderBottom:`2px solid ${V.border}`, borderRight:`1px solid ${V.border}`,
        cursor:"pointer", userSelect:"none",
        position:"sticky", top:26, zIndex:2,
        textAlign:"center", verticalAlign:"bottom",
        whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
      }}>
        <span style={{fontFamily:BODY,fontSize:14,fontWeight:700,color:active?V.orange:V.text}}>
          {f}{active&&<span style={{color:V.orange,marginLeft:2,fontSize:11}}>{sortDir===-1?"↓":"↑"}</span>}
        </span>
      </th>
    );
  };

  return (
    <div style={{fontFamily:BODY,background:V.bg,minHeight:"100vh"}}>

      {/* Header */}
      <div style={{
        background:"linear-gradient(135deg,#faf9f7 0%,#f5f0eb 40%,#E84C2A08 100%)",
        borderBottom:`1px solid ${V.border}`,
        padding:"16px 20px 14px",
        display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:10,
      }}>
        <div style={{display:"flex",alignItems:"center",gap:14}}>
          <img src={`data:image/png;base64,${VD_LOGO}`} alt="VD" style={{height:20,opacity:0.92}}/>
          <div style={{width:1,height:28,background:V.border}}/>
          <img src={`data:image/png;base64,${IS_LOGO}`} alt="IS" style={{height:18,opacity:0.85}}/>
          <div style={{width:1,height:34,background:V.border}}/>
          <div>
            <div style={{fontSize:20,fontWeight:700,color:V.text,letterSpacing:"-0.02em",lineHeight:1.1}}>13F Peer Matrix</div>
            <div style={{fontSize:12,color:V.muted,fontFamily:BODY,marginTop:2}}>
              __SF_NAME__ · SFID __SFID__ · <span style={{color:V.blue,fontWeight:700}}>__QUARTER__ 13F Data</span>
            </div>
          </div>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
          {[
            {bg:"#dcfce7",border:V.green,fg:V.green,label:"New position"},
            {bg:"#fee2e2",border:V.red,  fg:V.red,  label:"Liquidated (0.0%)"},
            {bg:V.bg,border:V.border,    fg:V.green,label:"▲ Increased"},
            {bg:V.bg,border:V.border,    fg:V.red,  label:"▼ Decreased"},
          ].map(it=>(
            <span key={it.label} style={{display:"flex",alignItems:"center",gap:5,fontSize:12,color:it.fg,fontWeight:700}}>
              <span style={{width:12,height:12,borderRadius:3,background:it.bg,border:`1.5px solid ${it.border}`,display:"inline-block",flexShrink:0}}/>
              {it.label}
            </span>
          ))}
          <div style={{fontSize:11,color:V.dim,fontFamily:BODY,marginLeft:4}}>Generated __GEN_DATE__</div>
        </div>
      </div>

      {/* Filter bar */}
      <div style={{padding:"8px 20px",display:"flex",alignItems:"center",gap:8,flexWrap:"wrap",borderBottom:`1px solid ${V.border}`,background:V.bg}}>
        <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search ticker or name…"
          style={{fontFamily:BODY,fontSize:13,padding:"5px 10px",border:`1px solid ${V.border}`,borderRadius:6,background:V.bg,color:V.text,width:220}}/>
        <span style={{fontSize:12,color:V.dim,fontFamily:BODY}}>{rows.length} names · {FUNDS.length} funds</span>
        {/* Metric toggle — fund columns show % of portfolio (default) or % of shares outstanding owned */}
        <div style={{display:"flex",border:`1px solid ${V.border}`,borderRadius:6,overflow:"hidden"}}>
          {["port","out"].map(m=>(
            <button key={m} onClick={()=>setMode(m)} title={METRICS[m].label} style={{
              fontFamily:BODY,fontSize:12,fontWeight:700,padding:"5px 12px",border:"none",cursor:"pointer",
              background:mode===m?V.blue:V.bg,color:mode===m?"#fff":V.muted,
            }}>{METRICS[m].short}</button>
          ))}
        </div>
        <div style={{marginLeft:"auto"}}>
          <button onClick={()=>xlsxOk&&exportXlsx(rows,FUNDS,mode)} style={{
            fontFamily:BODY,fontSize:13,fontWeight:700,padding:"5px 18px",borderRadius:6,border:"none",
            cursor:xlsxOk?"pointer":"not-allowed",background:xlsxOk?V.blue:"#d1d5db",color:"#fff",
          }}>↓ Export XLSX</button>
        </div>
      </div>

      {/* Ghost scrollbar on top — mirrors main scroll container */}
      <div
        ref={el=>topRef[0]=el}
        onScroll={syncTop}
        style={{overflowX:"auto",overflowY:"hidden",height:12,background:V.card,borderBottom:`1px solid ${V.border}`}}
      >
        <div style={{width:totalW+"px",height:1}}/>
      </div>

      {/* Main table — no bottom padding so scrollbar sits flush */}
      <div
        ref={el=>mainRef[0]=el}
        onScroll={syncMain}
        style={{overflowX:"auto",overflowY:"visible"}}
      >
        <table style={{borderCollapse:"collapse",tableLayout:"fixed",fontFamily:BODY,fontSize:13,width:totalW+"px"}}>
          <colgroup>
            <col style={{width:96}}/><col style={{width:240}}/>
            <col style={{width:96}}/><col style={{width:76}}/>
            <col style={{width:68}}/><col style={{width:116}}/>
            {FUNDS.map(f=><col key={f} style={{width:CW}}/>)}
          </colgroup>
          <thead>
            {/* Group label row */}
            <tr style={{height:26}}>
              <th colSpan={2} style={{padding:"4px 10px",fontSize:11,fontWeight:700,letterSpacing:"0.07em",textTransform:"uppercase",fontFamily:BODY,color:V.muted,background:V.card,textAlign:"left",borderBottom:`1px solid ${V.border}`,borderRight:`1px solid ${V.border}`,position:"sticky",top:0,zIndex:4}}>Company</th>
              <th colSpan={4} style={{padding:"4px 10px",fontSize:11,fontWeight:700,letterSpacing:"0.07em",textTransform:"uppercase",fontFamily:BODY,color:V.blue,background:V.card,textAlign:"center",borderBottom:`1px solid ${V.border}`,borderRight:`1px solid ${V.border}`,position:"sticky",top:0,zIndex:3}}>SuperFund Aggregates · SFID __SFID__</th>
              <th colSpan={FUNDS.length} style={{padding:"4px 10px",fontSize:11,fontWeight:700,letterSpacing:"0.07em",textTransform:"uppercase",fontFamily:BODY,color:V.orange,background:V.card,textAlign:"center",borderBottom:`1px solid ${V.border}`,position:"sticky",top:0,zIndex:3}}>{METRICS[mode].label} — __SF_NAME__ · __QUARTER__ vs __PRIOR_QUARTER__</th>
            </tr>
            {/* Column headers */}
            <tr>
              <Th col="ticker" sticky left={0}  style={{textAlign:"left"}}>Ticker</Th>
              <Th col="name"   sticky left={96} style={{textAlign:"left",borderRight:`2px solid ${V.border}`}}>Company</Th>
              <Th col="sfValue"  >Val ($M)</Th>
              <Th col="sfPctOut" >% Out</Th>
              <Th col="sfHolders"># Funds</Th>
              <Th col="_spark" style={{cursor:"default",borderRight:`2px solid ${V.border}`}}>
                SF Chart<br/><span style={{fontSize:10,fontWeight:400,color:V.dim}}>8-qtr shares</span>
              </Th>
              {FUNDS.map(f=><FundTh key={f} f={f}/>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r,i)=>{
              const alt=i%2===1;
              const rbg=alt?V.card:V.bg;
              const spark=SPARKDATA.data[r.ticker]||[];
              return (
                <tr key={r.ticker} style={{height:ROWH,background:rbg,borderBottom:`1px solid ${V.border}`}}>
                  <td style={{padding:"2px 10px",fontFamily:BODY,fontWeight:700,fontSize:14,color:V.text,position:"sticky",left:0,background:rbg,zIndex:1,borderRight:`1px solid ${V.border}`,whiteSpace:"nowrap"}}>{r.ticker}</td>
                  <td style={{padding:"2px 10px",fontSize:13,color:V.muted,position:"sticky",left:96,background:rbg,zIndex:1,borderRight:`2px solid ${V.border}`,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={r.name}>{r.name}</td>
                  <td style={{padding:"2px 8px",textAlign:"center",fontFamily:BODY,fontSize:13,color:V.text,borderRight:`1px solid ${V.border}`}}>{r.sfValue!=null?"$"+r.sfValue.toFixed(1)+"M":""}</td>
                  <td style={{padding:"2px 8px",textAlign:"center",fontFamily:BODY,fontSize:13,color:V.muted,borderRight:`1px solid ${V.border}`}}>{r.sfPctOut!=null?(r.sfPctOut*100).toFixed(1)+"%":""}</td>
                  <td style={{padding:"2px 8px",textAlign:"center",fontFamily:BODY,fontSize:14,fontWeight:r.sfHolders>=8?700:400,color:r.sfHolders>=8?V.blue:r.sfHolders>=5?V.text:V.dim,borderRight:`1px solid ${V.border}`}}>{r.sfHolders||""}</td>
                  <td style={{padding:"1px 4px",textAlign:"center",borderRight:`2px solid ${V.border}`}}><Sparkline series={spark}/></td>
                  {FUNDS.map(f=>{
                    const info=r.funds[f];
                    const cv=mval(info,mode);
                    const hasPct=cv!=null&&cv>0;
                    const isLiqd=info?.chg==="LIQUIDATED";
                    if(!info||(!hasPct&&!isLiqd&&!info.chg))
                      return <td key={f} style={{borderRight:`1px solid ${V.border}`,background:rbg}}/>;
                    const cs=CHG[info.chg]||{};
                    return (
                      <td key={f} style={{padding:"2px 4px",textAlign:"center",background:cs.bg||rbg,borderRight:`1px solid ${V.border}`}}>
                        <span style={{fontFamily:BODY,fontSize:13,fontWeight:700,color:cs.fg||V.text,whiteSpace:"nowrap"}}>
                          {isLiqd?(0).toFixed(METRICS[mode].dp)+"%":hasPct?cv.toFixed(METRICS[mode].dp)+"%":""}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={{borderTop:`1px solid ${V.border}`,padding:"12px 20px",display:"flex",alignItems:"center",justifyContent:"space-between",background:V.card}}>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          <img src={`data:image/png;base64,${IS_LOGO}`} alt="" style={{height:13,opacity:0.4}}/>
          <span style={{fontSize:10,color:V.dim,fontFamily:BODY}}>Data: InsiderScore/VerityData MCP · Excl. puts/calls · Sparkline = SF aggregate shares __SPARK_RANGE__ · See disclaimers on InsiderScore.com</span>
        </div>
        <a href="mailto:bsilverman@verityplatform.com" style={{fontSize:12,color:V.orange,textDecoration:"none",fontWeight:700,fontFamily:BODY}}>Feedback</a>
      </div>
    </div>
  );
}
