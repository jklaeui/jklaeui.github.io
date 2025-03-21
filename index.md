# Welcome to my webpage!

- I'm a post doc in Economics at CREST in Paris (ENSAE / IP). In my research, I use data from online job search and recruitment to investigate how labour market imperfections shape job finding and wages
- I obtained my PhD from the University of Lausanne under supervision of [Rafael Lalive](https://sites.google.com/site/rafaellalive/) and [Michael Siegenthaler](https://sites.google.com/site/siegenthalermichael/home). I visited the LSE (CEP), on the invitation of [Alan Manning](https://en.wikipedia.org/wiki/Alan_Manning) and ETH Zurich (KOF Swiss Economic Institute) invited by Michael Siegenthaler

***

## Research 


####  Labor market imbalances, job search scopes and job finding
In progress; solo-authored

*Presented at PSE Applied Economics Lunch (Feb 2025), EALE 2024 Bergen (Sep 2024), SKILS Ski and Labor Seminar Lenzerheide (Jan 2024), IZA Workshop: Matching Workers and Jobs Online (Sep 2023), LSE Labour WIP Seminar (Mar 2023)*

<button class="show-button" onclick="toggleAbstract('abstract_click_search_scopes')">Show abstract</button>
<div id="abstract_click_search_scopes" class="abstract">
 This paper investigates how jobseekers adjust the breadth of their search across different segments of the labour market and how such adjustments affect employment outcomes. Imbalances often exist between jobseekers and vacancies in certain occupations or regions, potentially creating opportunities for jobseekers to adjust their search strategies and target segments where demand for them is high.
 I use a unique dataset that combines administrative unemployment records with detailed click data on job postings to measure search scope. I focus on two dimensions of breadth: the distance between a jobseeker’s residence and the posted job, and the local labour market tightness in the commuting zone–occupation segments. A key challenge is that jobseekers self-select into their search strategies. To address this, I exploit exogenous variation in the assignment of jobseekers to caseworkers, whose distinct tendencies influence jobseekers’ subsequent search patterns. I then link these caseworker-induced shifts in search scope to unemployment duration and job quality. My findings suggest that encouraging broader job search or targeting sectors with high labour demand surpluses has measurable effects on reemployment prospects and can alleviate mismatches between labour supply and demand. These results provide policy-relevant insights on how targeted counselling can shape jobseekers’ behaviour and improve labour market efficiency.
 </div>


#### Job Search and Employer Market Power
In progress; with I. Bassier, A. Manning

<button class="show-button" onclick="toggleAbstract('abstract_click_monopsony')">Show abstract</button>
<div id="abstract_click_monopsony" class="abstract">
This paper provides a framework for thinking about how the job search of workers affects the market power of employers. We present a way of thinking about this which encapsulates popular existing models in which employer market power is based on either frictions in labor markets or imperfect substitutability among jobs. We show how this model can be used to compute measures of the extent of employer market power and relates them to popularly used measures of concentration ratios. We use data on the search behaviour of Swiss unemployed to investigate the number of employers being considered by job-seekers using 'clicks' on vacancies to define consideration sets. 
</div>

#### Adapting to Scarcity: The Role of Firms in Occupational Transitions
In progress; with D. Kopp, R. Lalive, M. Siegenthaler

*Presented at ZEW Mannheim Research Seminar (Mar 2025), IZA Summer School in Labor Economics (June 2023)*

<button class="show-button" onclick="toggleAbstract('abstract_click_occ_mob')">Show abstract</button>
<div id="abstract_click_occ_mob" class="abstract">
This paper investigates how recruiters shape occupational mobility in the labor market. Prior research has emphasized workers’ decisions, largely overlooking the role of firms. We leverage unique click data from a recruitment platform. Our identification strategy exploits the fact that we can see the same applicant information that recruiters observe, making selection on observables plausible. We find that recruiters strongly favor candidates whose current occupation matches the advertised job. Nevertheless, non-matching candidates also have substantial hiring probabilities. Finally, we show that recruiters adjust their hiring patterns to occupational labor market tightness partially offseting occupational scarcity. Our estimates suggest that recruiter decisions account for roughly one third of occupational transitions. 
</div>


***

## Policy and tools

#### Swiss Job Tracker

- [A real-time index of open vacancy postings in Switzerland](http://swissjobtracker.ch/)
- [Github](https://github.com/swissjobtracker/chjobtracker): R-code aggregating the scraped data from 70 job portals and 50K company webpages. I implemented an algorithm that deals with scraper issues and unstable job portals in real-time to obtain a clean index.

#### Policy reports & Media

- [NZZaS: Studie zur zweiten Welle: 200 000 Selbständige fürchten um ihre Existenz](https://nzzas.nzz.ch/wirtschaft/zweite-welle-viele-selbstaendige-fuerchten-um-ihre-existenz-ld.1589295). 
- [Launch Swissjobtracker on Swissinfo (SRG SSR)](https://www.swissinfo.ch/fre/toute-l-actu-en-bref/repli-du-nombre-d-offres-d-emplois-en-d%C3%A9cembre--%C3%A9tude-/48136458)

#### Teaching

- During PhD: [Econometrics at the master's level (Course by Prof. M. Huber)](https://hecnet.unil.ch/hec/syllabus/descriptif/2551?dyn_lang=en)

### Other

- Together with Pascal Josephy, I founded the web design and web development agency jkweb in 2011 (at the age of 17). The company by now employs over 30 programmers, designers and other specialists in Zurich and Basel. jkweb has recently acquired novu and is now called [novu](https://novu.ch/). 

***

<script>
    // JavaScript function to toggle visibility
    function toggleAbstract(id) {
        const abstract = document.getElementById(id);
        if (abstract.style.display === "none" || abstract.style.display === "") {
            abstract.style.display = "block";
             gtag('event', id);
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
        background-color: #2776b8;
        color: white;
  padding: 5px;
  border: none;
  border-radius: 3px;
  font-size: 13px;
      }
      
   .show-button:hover {
        background-color: #0056b3;
    }
</style>