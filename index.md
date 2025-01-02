# Welcome to my webpage!

- I'm a post doc in Economics at CREST in Paris (ENSAE / IP). In my research, I use data from online job search and recruitment to investigate how labour market imperfections shape job finding and wages
- I obtained my PhD from the University of Lausanne under supervision of [Rafael Lalive](https://sites.google.com/site/rafaellalive/) and [Michael Siegenthaler](https://kof.ethz.ch/en/the-institute/kof-divisions/research-division-labour-market-economics.html). I visited the LSE (CEP), on the invitation of [Alan Manning](https://en.wikipedia.org/wiki/Alan_Manning) and ETH Zurich (KOF Swiss Economic Institute) invited by Michael Siegenthaler

***

## Research 

### Adapting to Scarcity: Job Search and Recruiting Across Occupational Boundaries *(in progress; with D. Kopp, R. Lalive, M. Siegenthaler)*

<button class="show-button" onclick="toggleAbstract('abstract1')">Click here to see abstract</button>
<div id="abstract1" class="abstract">
    This paper investigates how job seekers adapt their search strategies when confronted with occupational scarcity, focusing on transitions across occupational boundaries. We use unique data combining job search activity and recruitment outcomes to identify the role of adaptability in shaping labor market outcomes.
</div>

### Consideration scopes in job search *(in progress; solo-authored)*

<button class="show-button" onclick="toggleAbstract('abstract2')">Click here to see abstract</button>
<div id="abstract2" class="abstract">
    This paper explores how job seekers form their consideration sets when searching for jobs and examines the implications of consideration scope on labor market outcomes. The study uses a novel dataset on online job search behavior.
</div>

### Job Search and Employer Market Power *(in progress; with I. Bassier, A. Manning)*

<button class="show-button" onclick="toggleAbstract('abstract3')">Click here to see abstract</button>
<div id="abstract3" class="abstract">
    This paper examines how employer market power influences job search behavior and outcomes. Using unique data and structural modeling, we quantify the extent of employer power and its implications for job seekers.
</div>

***

## Policy and tools

### Swiss Job Tracker

- [A real-time index of open vacancy postings in Switzerland](http://swissjobtracker.ch/)
- [Github](https://github.com/swissjobtracker/chjobtracker): R-code aggregating the scraped data from 70 job portals and 50K company webpages. I implemented an algorithm that deals with scraper issues and unstable job portals in real-time to obtain a clean index.

### Policy reports & Media

- [NZZaS: Studie zur zweiten Welle: 200 000 Selbständige fürchten um ihre Existenz](https://nzzas.nzz.ch/wirtschaft/zweite-welle-viele-selbstaendige-fuerchten-um-ihre-existenz-ld.1589295). 
- [Launch Swissjobtracker on Swissinfo (SRG SSR)](https://www.swissinfo.ch/fre/toute-l-actu-en-bref/repli-du-nombre-d-offres-d-emplois-en-d%C3%A9cembre--%C3%A9tude-/48136458)

### Teaching

- [Econometrics at the master's level (Course by Prof. M. Huber)](https://hecnet.unil.ch/hec/syllabus/descriptif/2551?dyn_lang=en)

### Other

- Together with Pascal Josephy, I founded the web design and web development agency jkweb in 2011 (at the age of 17). The company by now employs over 30 programmers, designers and other specialists in Zurich and Basel. jkweb has recently acquired novu and is now called [novu](https://novu.ch/). 

***

<script>
    // JavaScript function to toggle visibility
    function toggleAbstract(id) {
        const abstract = document.getElementById(id);
        if (abstract.style.display === "none" || abstract.style.display === "") {
            abstract.style.display = "block";
        } else {
            abstract.style.display = "none";
        }
    }
</script>

<style>
    /* CSS for styling */
    .abstract {
        display: none; /* Abstracts are hidden by default */
        margin: 10px 0;
        padding: 10px;
        background-color: #f9f9f9;
        border: 1px solid #ddd;
    }
    .show-button {
        cursor: pointer;
        background-color: #007bff;
        color: white;
        padding: 10px;
        border: none;
        border-radius: 5px;
    }
    .show-button:hover {
        background-color: #0056b3;
    }
</style>