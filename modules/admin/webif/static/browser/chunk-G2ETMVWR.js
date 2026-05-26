import{Sa as I,Va as M,Ya as B,Za as N,_a as i,p as D}from"./chunk-DIKIFGDA.js";import{Cb as l,Db as h,Eb as k,Fb as v,Sa as m,X as c,_ as d,aa as s,ac as b,dc as o,gb as g,ia as f,kb as u,lb as y,pc as S,ta as a,tb as p}from"./chunk-PQXDUQP4.js";var E=`
    .p-progressspinner {
        position: relative;
        margin: 0 auto;
        width: 100px;
        height: 100px;
        display: inline-block;
    }

    .p-progressspinner::before {
        content: '';
        display: block;
        padding-top: 100%;
    }

    .p-progressspinner-spin {
        height: 100%;
        transform-origin: center center;
        width: 100%;
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        right: 0;
        margin: auto;
        animation: p-progressspinner-rotate 2s linear infinite;
    }

    .p-progressspinner-circle {
        stroke-dasharray: 89, 200;
        stroke-dashoffset: 0;
        stroke: dt('progressspinner.colorOne');
        animation:
            p-progressspinner-dash 1.5s ease-in-out infinite,
            p-progressspinner-color 6s ease-in-out infinite;
        stroke-linecap: round;
    }

    @keyframes p-progressspinner-rotate {
        100% {
            transform: rotate(360deg);
        }
    }
    @keyframes p-progressspinner-dash {
        0% {
            stroke-dasharray: 1, 200;
            stroke-dashoffset: 0;
        }
        50% {
            stroke-dasharray: 89, 200;
            stroke-dashoffset: -35px;
        }
        100% {
            stroke-dasharray: 89, 200;
            stroke-dashoffset: -124px;
        }
    }
    @keyframes p-progressspinner-color {
        100%,
        0% {
            stroke: dt('progressspinner.color.one');
        }
        40% {
            stroke: dt('progressspinner.color.two');
        }
        66% {
            stroke: dt('progressspinner.color.three');
        }
        80%,
        90% {
            stroke: dt('progressspinner.color.four');
        }
    }
`;var w={root:()=>["p-progressspinner"],spin:"p-progressspinner-spin",circle:"p-progressspinner-circle"},C=(()=>{class n extends M{name="progressspinner";style=E;classes=w;static \u0275fac=(()=>{let r;return function(e){return(r||(r=a(n)))(e||n)}})();static \u0275prov=c({token:n,factory:n.\u0275fac})}return n})();var F=new d("PROGRESSSPINNER_INSTANCE"),U=(()=>{class n extends N{$pcProgressSpinner=s(F,{optional:!0,skipSelf:!0})??void 0;bindDirectiveInstance=s(i,{self:!0});styleClass;strokeWidth="2";fill="none";animationDuration="2s";ariaLabel;onAfterViewChecked(){this.bindDirectiveInstance.setAttrs(this.ptms(["host","root"]))}_componentStyle=s(C);static \u0275fac=(()=>{let r;return function(e){return(r||(r=a(n)))(e||n)}})();static \u0275cmp=g({type:n,selectors:[["p-progressSpinner"],["p-progress-spinner"],["p-progressspinner"]],hostVars:5,hostBindings:function(t,e){t&2&&(p("aria-label",e.ariaLabel)("role","progressbar")("aria-busy",!0),o(e.cn(e.cx("root"),e.styleClass)))},inputs:{styleClass:"styleClass",strokeWidth:"strokeWidth",fill:"fill",animationDuration:"animationDuration",ariaLabel:"ariaLabel"},features:[S([C,{provide:F,useExisting:n},{provide:B,useExisting:n}]),y([i]),u],decls:2,vars:10,consts:[["viewBox","25 25 50 50",3,"pBind"],["cx","50","cy","50","r","20","stroke-miterlimit","10",3,"pBind"]],template:function(t,e){t&1&&(f(),h(0,"svg",0),v(1,"circle",1),k()),t&2&&(o(e.cx("spin")),b("animation-duration",e.animationDuration),l("pBind",e.ptm("spin")),m(),o(e.cx("circle")),l("pBind",e.ptm("circle")),p("fill",e.fill)("stroke-width",e.strokeWidth))},dependencies:[D,I,i],encapsulation:2,changeDetection:0})}return n})();export{U as a};
