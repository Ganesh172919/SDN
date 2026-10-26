"""Local, renderer-independent flow graphic for the Markdown/Rmd navigation."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
def main():
    folder=ROOT/'docs/images';folder.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(12,10));ax.set(xlim=(0,14),ylim=(0,12));ax.axis('off')
    fig.subplots_adjust(left=.02,right=.98,top=.94,bottom=.02)
    def box(x,y,w,h,title,body,fill='#e8f0e9'):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08,rounding_size=0.07',facecolor=fill,edgecolor='#007d76',lw=1.3))
        ax.text(x+w/2,y+h*.69,title,ha='center',va='center',fontsize=13,fontweight='bold',color='#102e36')
        ax.text(x+w/2,y+h*.31,body,ha='center',va='center',fontsize=10,color='#37585e')
    def arrow(a,b):ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':'#007d76','lw':1.4})
    ax.text(7,11.65,'SELF-X: complete local control and evidence flow',ha='center',fontsize=20,fontweight='bold',color='#102e36')
    stages=[('1  Observe','Seeded rates, flow match and queues'),('2  Retrieve','Context + action + meter-parameter evidence'),('3  Suggest','Local rule, supported memory, cache or API'),('4  Validate','Known flow / port; 20% drop and 90% route bounds'),('5  Install and expire','Simulated OpenFlow ADD; hard_timeout = 5 s'),('6  Measure and reflect','Delivery, delay, total loss and observed reward')]
    ys=[10,8.3,6.6,4.9,3.2,1.5]
    for i,((title,body),y) in enumerate(zip(stages,ys)):
        box(4.3,y,5.4,1.05,title,body)
        if i<5:arrow((7,y),(7,ys[i+1]+1.13))
    box(.2,8.3,3.3,1.05,'Self-embedding memory','128 prior completed episodes\n3 observations per parameter')
    arrow((3.6,8.82),(4.2,8.82))
    box(10.5,6.45,3.2,1.35,'Actual provider calls','Gemini / free OpenRouter\n3.8 s cancellable pooled worker\nTimeout / deferral stays explicit')
    arrow((9.8,7.13),(10.4,7.13))
    ax.plot([7,.1,.1,1.85],[1.42,1.42,7.9,7.9],color='#007d76',lw=1.2)
    arrow((1.85,7.9),(1.85,8.2));ax.text(.24,5.2,'Store measured feedback',rotation=90,fontsize=10,color='#37585e',va='center')
    box(10.5,1.35,3.2,1.35,'Review and reproduce','Raw CSV / JSON + rule audit\nDashboard replay / PNG / SVG\nEditable DOCX / PPTX + PDFs')
    arrow((9.8,2.02),(10.4,2.02))
    ax.text(7,.45,'All network outcomes and rule installations are simulated; API requests are real.\nProject files and outputs stay inside selfx. No physical switch is contacted.',ha='center',fontsize=11,color='#536c70')
    fig.savefig(folder/'architecture.png',dpi=170,facecolor='white');fig.savefig(folder/'architecture.svg',facecolor='white');plt.close(fig)
    for name in ('ARCHITECTURE.md','ARCHITECTURE.Rmd'):
        path=ROOT/'docs'/name;s=path.read_text(encoding='utf-8');needle='## Complete flow\n\n'
        if 'images/architecture.png' not in s:s=s.replace(needle,needle+'![Complete control and evidence flow](images/architecture.png)\n\n')
        path.write_text(s,encoding='utf-8')
    print('Created local architecture PNG/SVG and linked Markdown/Rmd flow.')

if __name__=='__main__':main()
