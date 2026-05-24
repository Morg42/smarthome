import{i as J,t as K}from"./chunk-PGMSWMXR.js";import{g as U}from"./chunk-LVW3PW3N.js";import{$a as W,Ra as R,Sa as $,Va as q,Ya as P,_a as d,l as j,p as G}from"./chunk-DBIFYEB3.js";import{Cb as r,Db as f,Eb as m,Kc as z,Lb as A,Mb as L,Qb as k,Rc as v,Sa as c,Sb as D,Sc as x,Vb as y,W as C,Wb as N,X as T,Xa as S,Xb as g,Yb as h,_,aa as a,cc as H,dc as s,ga as u,gb as V,ha as p,kb as E,lb as B,mb as M,pc as O,rc as Q,ta as w,tb as b,wb as I,xb as F}from"./chunk-PQXDUQP4.js";var X=`
    .p-toggleswitch {
        display: inline-block;
        width: dt('toggleswitch.width');
        height: dt('toggleswitch.height');
    }

    .p-toggleswitch-input {
        cursor: pointer;
        appearance: none;
        position: absolute;
        top: 0;
        inset-inline-start: 0;
        width: 100%;
        height: 100%;
        padding: 0;
        margin: 0;
        opacity: 0;
        z-index: 1;
        outline: 0 none;
        border-radius: dt('toggleswitch.border.radius');
    }

    .p-toggleswitch-slider {
        cursor: pointer;
        width: 100%;
        height: 100%;
        border-width: dt('toggleswitch.border.width');
        border-style: solid;
        border-color: dt('toggleswitch.border.color');
        background: dt('toggleswitch.background');
        transition:
            background dt('toggleswitch.transition.duration'),
            color dt('toggleswitch.transition.duration'),
            border-color dt('toggleswitch.transition.duration'),
            outline-color dt('toggleswitch.transition.duration'),
            box-shadow dt('toggleswitch.transition.duration');
        border-radius: dt('toggleswitch.border.radius');
        outline-color: transparent;
        box-shadow: dt('toggleswitch.shadow');
    }

    .p-toggleswitch-handle {
        position: absolute;
        top: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        background: dt('toggleswitch.handle.background');
        color: dt('toggleswitch.handle.color');
        width: dt('toggleswitch.handle.size');
        height: dt('toggleswitch.handle.size');
        inset-inline-start: dt('toggleswitch.gap');
        margin-block-start: calc(-1 * calc(dt('toggleswitch.handle.size') / 2));
        border-radius: dt('toggleswitch.handle.border.radius');
        transition:
            background dt('toggleswitch.transition.duration'),
            color dt('toggleswitch.transition.duration'),
            inset-inline-start dt('toggleswitch.slide.duration'),
            box-shadow dt('toggleswitch.slide.duration');
    }

    .p-toggleswitch.p-toggleswitch-checked .p-toggleswitch-slider {
        background: dt('toggleswitch.checked.background');
        border-color: dt('toggleswitch.checked.border.color');
    }

    .p-toggleswitch.p-toggleswitch-checked .p-toggleswitch-handle {
        background: dt('toggleswitch.handle.checked.background');
        color: dt('toggleswitch.handle.checked.color');
        inset-inline-start: calc(dt('toggleswitch.width') - calc(dt('toggleswitch.handle.size') + dt('toggleswitch.gap')));
    }

    .p-toggleswitch:not(.p-disabled):has(.p-toggleswitch-input:hover) .p-toggleswitch-slider {
        background: dt('toggleswitch.hover.background');
        border-color: dt('toggleswitch.hover.border.color');
    }

    .p-toggleswitch:not(.p-disabled):has(.p-toggleswitch-input:hover) .p-toggleswitch-handle {
        background: dt('toggleswitch.handle.hover.background');
        color: dt('toggleswitch.handle.hover.color');
    }

    .p-toggleswitch:not(.p-disabled):has(.p-toggleswitch-input:hover).p-toggleswitch-checked .p-toggleswitch-slider {
        background: dt('toggleswitch.checked.hover.background');
        border-color: dt('toggleswitch.checked.hover.border.color');
    }

    .p-toggleswitch:not(.p-disabled):has(.p-toggleswitch-input:hover).p-toggleswitch-checked .p-toggleswitch-handle {
        background: dt('toggleswitch.handle.checked.hover.background');
        color: dt('toggleswitch.handle.checked.hover.color');
    }

    .p-toggleswitch:not(.p-disabled):has(.p-toggleswitch-input:focus-visible) .p-toggleswitch-slider {
        box-shadow: dt('toggleswitch.focus.ring.shadow');
        outline: dt('toggleswitch.focus.ring.width') dt('toggleswitch.focus.ring.style') dt('toggleswitch.focus.ring.color');
        outline-offset: dt('toggleswitch.focus.ring.offset');
    }

    .p-toggleswitch.p-invalid > .p-toggleswitch-slider {
        border-color: dt('toggleswitch.invalid.border.color');
    }

    .p-toggleswitch.p-disabled {
        opacity: 1;
    }

    .p-toggleswitch.p-disabled .p-toggleswitch-slider {
        background: dt('toggleswitch.disabled.background');
    }

    .p-toggleswitch.p-disabled .p-toggleswitch-handle {
        background: dt('toggleswitch.handle.disabled.background');
    }
`;var te=["handle"],ie=["input"],ne=t=>({checked:t});function oe(t,ee){t&1&&A(0)}function le(t,ee){if(t&1&&M(0,oe,1,0,"ng-container",3),t&2){let i=D();r("ngTemplateOutlet",i.handleTemplate||i._handleTemplate)("ngTemplateOutletContext",Q(2,ne,i.checked()))}}var re=`
    ${X}

    p-toggleswitch.ng-invalid.ng-dirty > .p-toggleswitch-slider {
        border-color: dt('toggleswitch.invalid.border.color');
    }
`,se={root:{position:"relative"}},de={root:({instance:t})=>["p-toggleswitch p-component",{"p-toggleswitch p-component":!0,"p-toggleswitch-checked":t.checked(),"p-disabled":t.$disabled(),"p-invalid":t.invalid()}],input:"p-toggleswitch-input",slider:"p-toggleswitch-slider",handle:"p-toggleswitch-handle"},Y=(()=>{class t extends q{name="toggleswitch";style=re;classes=de;inlineStyles=se;static \u0275fac=(()=>{let i;return function(e){return(i||(i=w(t)))(e||t)}})();static \u0275prov=T({token:t,factory:t.\u0275fac})}return t})();var Z=new _("TOGGLESWITCH_INSTANCE"),ae={provide:U,useExisting:C(()=>ce),multi:!0},ce=(()=>{class t extends K{$pcToggleSwitch=a(Z,{optional:!0,skipSelf:!0})??void 0;bindDirectiveInstance=a(d,{self:!0});onAfterViewChecked(){this.bindDirectiveInstance.setAttrs(this.ptms(["host","root"]))}styleClass;tabindex;inputId;readonly;trueValue=!0;falseValue=!1;ariaLabel;size=z();ariaLabelledBy;autofocus;onChange=new S;input;handleTemplate;_handleTemplate;focused=!1;_componentStyle=a(Y);templates;onHostClick(i){this.onClick(i)}onAfterContentInit(){this.templates.forEach(i=>{i.getType()==="handle"?this._handleTemplate=i.template:this._handleTemplate=i.template})}onClick(i){!this.$disabled()&&!this.readonly&&(this.writeModelValue(this.checked()?this.falseValue:this.trueValue),this.onModelChange(this.modelValue()),this.onChange.emit({originalEvent:i,checked:this.modelValue()}),this.input.nativeElement.focus())}onFocus(){this.focused=!0}onBlur(){this.focused=!1,this.onModelTouched()}checked(){return this.modelValue()===this.trueValue}writeControlValue(i,n){n(i),this.cd.markForCheck()}static \u0275fac=(()=>{let i;return function(e){return(i||(i=w(t)))(e||t)}})();static \u0275cmp=V({type:t,selectors:[["p-toggleswitch"],["p-toggleSwitch"],["p-toggle-switch"]],contentQueries:function(n,e,o){if(n&1&&(y(o,te,4),y(o,R,4)),n&2){let l;g(l=h())&&(e.handleTemplate=l.first),g(l=h())&&(e.templates=l)}},viewQuery:function(n,e){if(n&1&&N(ie,5),n&2){let o;g(o=h())&&(e.input=o.first)}},hostVars:5,hostBindings:function(n,e){n&1&&k("click",function(l){return e.onHostClick(l)}),n&2&&(b("data-pc-name","toggleswitch"),H(e.sx("root")),s(e.cn(e.cx("root"),e.styleClass)))},inputs:{styleClass:"styleClass",tabindex:[2,"tabindex","tabindex",x],inputId:"inputId",readonly:[2,"readonly","readonly",v],trueValue:"trueValue",falseValue:"falseValue",ariaLabel:"ariaLabel",size:[1,"size"],ariaLabelledBy:"ariaLabelledBy",autofocus:[2,"autofocus","autofocus",v]},outputs:{onChange:"onChange"},features:[O([ae,Y,{provide:Z,useExisting:t},{provide:P,useExisting:t}]),B([d]),E],decls:5,vars:20,consts:[["input",""],["type","checkbox","role","switch",3,"focus","blur","checked","pAutoFocus","pBind"],[3,"pBind"],[4,"ngTemplateOutlet","ngTemplateOutletContext"]],template:function(n,e){if(n&1){let o=L();f(0,"input",1,0),k("focus",function(){return u(o),p(e.onFocus())})("blur",function(){return u(o),p(e.onBlur())}),m(),f(2,"div",2)(3,"div",2),I(4,le,1,4,"ng-container"),m()()}n&2&&(s(e.cx("input")),r("checked",e.checked())("pAutoFocus",e.autofocus)("pBind",e.ptm("input")),b("id",e.inputId)("required",e.required()?"":void 0)("disabled",e.$disabled()?"":void 0)("aria-checked",e.checked())("aria-labelledby",e.ariaLabelledBy)("aria-label",e.ariaLabel)("name",e.name())("tabindex",e.tabindex),c(2),s(e.cx("slider")),r("pBind",e.ptm("slider")),c(),s(e.cx("handle")),r("pBind",e.ptm("handle")),c(),F(e.handleTemplate||e._handleTemplate?4:-1))},dependencies:[G,j,J,$,W,d],encapsulation:2,changeDetection:0})}return t})();export{ce as a};
