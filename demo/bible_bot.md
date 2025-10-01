---
marp: true
style: |
  /* Target all slides except the title slide */
  section:not(.title) h1 {
    position: fixed;
    top: 20px; /* Adjust distance from top */
    left: 20px; /* Adjust distance from left */
    margin: 0;
    padding: 10px;
    text-align: center;
    background: #f0f0f0; /* Optional: Add background for visibility */
    width: calc(100% - 60px); /* Ensure it spans the slide width */
    z-index: 10; /* Ensure heading is above other content */
  }
  /* Adjust content to avoid overlap with fixed heading */
  section:not(.title) {
    padding-top: 110px; /* Add padding to prevent content from being hidden under the heading */
  }
---
<!-- _class: title -->
__Bible translation challenge__
&nbsp;

# Empowering Bible translation with crowdsourced data
## &mdash; A WhatsApp chatbot to collect user input for low-resource languages

&nbsp;

by Joshua & Siwei
Oct 9, 2025

***
<!-- paginate: true -->

# __Linguists' wish:__ as many datapoints as possible


***
# Upload data
![bg w:90% supabse](supabase.png)


***
# __Gloo AI__ for recommendation and cleaning