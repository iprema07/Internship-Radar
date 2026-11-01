# Fast updates and freshness

This project checks pinned public employer boards on a **15-minute GitHub Actions schedule** and scans a rotating batch of **500 catalog boards hourly**. Employers with previously relevant directory matches are also monitored in the priority scan. For a 2,000-board catalog, all boards are scheduled in four hourly rotations under normal operation.

**Not real-time:** Job-board APIs can lag employer publication; GitHub Actions can delay or skip scheduled runs; Pages and browser caches can lag too. A new job may be found after someone else has already applied. An employer's direct job link remains the application source of truth.


